#!/bin/bash

### Run OCR training on a DigitalOcean droplet from this computer.
#
# Needs: doctl (authenticated with "doctl auth init"), ssh, rsync.
#
# Typical use:
#   cloud.sh up                       # create droplet + run setup.sh on it
#   cloud.sh train -n 100000          # start scripts/train.sh there, detached in screen
#   cloud.sh status                   # latest progress
#   cloud.sh down                     # fetch results, then destroy the droplet
#
# Settings can be given as environment variables or in ~/.config/ocr-cloud.conf
# (a bash file of VAR=value lines; keep it private if OCR_PAT is in it):
#   DO_NAME      droplet name [ocr-train]
#   DO_SIZE      droplet size slug [c-8]; list them with: doctl compute size list
#   DO_REGION    region slug [fra1]
#   DO_IMAGE     image slug [ubuntu-24-04-x64]
#   DO_SSH_KEY   public key file whose key the droplet gets [~/.ssh/id_ed25519.pub or id_rsa.pub]
#   OCR_BRANCH   branch of the ocr repo to clone [default branch]
#   OCR_PAT      GitHub token for the private ocr-example-docs repo [asked for if unset]
#   RESULTS_DIR  where "fetch" puts results [~/ocr-cloud-results]

set -o pipefail

conf="${HOME}/.config/ocr-cloud.conf"
# shellcheck source=/dev/null
[[ -r $conf ]] && source "$conf"

DO_NAME="${DO_NAME:-ocr-train}"
DO_SIZE="${DO_SIZE:-s-4vcpu-8gb}"
DO_REGION="${DO_REGION:-fra1}"
DO_IMAGE="${DO_IMAGE:-ubuntu-24-04-x64}"
RESULTS_DIR="${RESULTS_DIR:-${HOME}/ocr-cloud-results}"
OCR_REPO_URL="https://github.com/sil-car/ocr.git"
tag="ocr-train"          # droplets with this tag get the firewall below
firewall_name="ocr-train"
screen_name="ocr-train"  # must match train.sh
local_repo="$(dirname "$(dirname "$(readlink -f "$0")")")"
state_dir="${HOME}/.cache/ocr-cloud"
known_hosts="${state_dir}/known_hosts"

usage="usage: $0 [-N NAME] COMMAND [ARGS]

Droplet:
  up [-s SIZE] [-r REGION] [-b BRANCH]
            create the droplet (with firewall and SSH key) and run setup on it
  setup     (re)run the setup on an existing droplet
  down [-n] [-y]
            fetch results (skip with -n), then destroy the droplet;
            -y: don't ask, even if training is still running
  list      list all droplets tagged \"${tag}\" (to catch forgotten ones)

Training:
  train [TRAIN.SH ARGS]
            start scripts/train.sh on the droplet, detached in screen
            (e.g. \"$0 train -n 100000 -L Lfx1152\"; see train.sh -h)
  status    is training running; latest lines of the newest log
  attach [SESSION]
            attach to the training screen session (detach with Ctrl-a d);
            with SESSION, attach to that screen session instead, creating it
            if needed (for other work while training runs)
  fetch     copy logs, models and checkpoints to ${RESULTS_DIR}/NAME/
  update    git pull the ocr repo on the droplet
  sync      copy this computer's scripts/ folder to the droplet (to try
            changes before pushing them)

Other:
  ssh [CMD] log in to the droplet (or run CMD there)
  ip        print the droplet's IP address

Options:
  -N NAME   act on droplet NAME instead of \"${DO_NAME}\" (to run several)
  -h        show this help

Settings are read from the environment or ${conf}; see the top of this script.
"

die() { echo "Error: $*" >&2; exit 1; }
info() { echo "==> $*"; }

while getopts ":N:h" opt; do
    case $opt in
        N) DO_NAME="$OPTARG" ;;
        h) echo "$usage"; exit 0 ;;
        *) echo "$usage"; exit 1 ;;
    esac
done
shift $((OPTIND - 1))
cmd="$1"
[[ -n $cmd ]] || { echo "$usage"; exit 1; }
shift

need() { command -v "$1" >/dev/null || die "\"$1\" is not installed."; }
need doctl
need ssh
mkdir -p "$state_dir"

### Helpers.

droplet_ip() {
    doctl compute droplet list --tag-name "$tag" --format Name,PublicIPv4 --no-header \
        | awk -v n="$DO_NAME" '$1 == n { print $2; exit }'
}

require_ip() {
    ip="$(droplet_ip)"
    [[ -n $ip ]] || die "no droplet named \"$DO_NAME\" (tag \"$tag\"). Create one with: $0 up"
}

# Known hosts are kept apart from ~/.ssh/known_hosts, because droplet IPs get
# reused with new host keys.
ssh_opts=(
    -o StrictHostKeyChecking=accept-new
    -o UserKnownHostsFile="$known_hosts"
    -o ServerAliveInterval=30
)

on_droplet() {  # run a command on the droplet: on_droplet [ssh opts] -- CMD
    local opts=()
    while [[ $1 != -- ]]; do opts+=("$1"); shift; done
    shift
    ssh "${ssh_opts[@]}" "${opts[@]}" "root@${ip}" "$@"
}

ssh_key_fingerprint() {
    local key="$DO_SSH_KEY"
    if [[ -z $key ]]; then
        for k in "${HOME}/.ssh/id_ed25519.pub" "${HOME}/.ssh/id_rsa.pub"; do
            [[ -r $k ]] && { key="$k"; break; }
        done
    fi
    [[ -r $key ]] || die "no SSH public key found; set DO_SSH_KEY."
    local fp
    fp="$(ssh-keygen -E md5 -lf "$key" | awk '{print $2}')"
    fp="${fp#MD5:}"
    if ! doctl compute ssh-key list --format FingerPrint --no-header | grep -qx "$fp"; then
        die "the key $key isn't in your DigitalOcean account. Add it with:
  doctl compute ssh-key import $(hostname)-key --public-key-file $key"
    fi
    echo "$fp"
}

ensure_firewall() {
    doctl compute tag create "$tag" >/dev/null 2>&1 || true
    if doctl compute firewall list --format Name --no-header | grep -qx "$firewall_name"; then
        return
    fi
    info "Creating firewall \"$firewall_name\" (SSH in, everything out) for tag \"$tag\""
    local any="address:0.0.0.0/0,address:::/0"
    doctl compute firewall create \
        --name "$firewall_name" \
        --tag-names "$tag" \
        --inbound-rules "protocol:tcp,ports:22,${any}" \
        --outbound-rules "protocol:tcp,ports:all,${any} protocol:udp,ports:all,${any} protocol:icmp,${any}" \
        >/dev/null || die "couldn't create the firewall."
}

wait_for_ssh() {
    info "Waiting for SSH on $ip"
    for _ in $(seq 60); do
        if on_droplet -o ConnectTimeout=5 -o BatchMode=yes -- true 2>/dev/null; then
            return 0
        fi
        sleep 5
    done
    die "SSH on $ip didn't come up."
}

get_pat() {
    if [[ -z $OCR_PAT ]]; then
        # Not needed if the droplet already has the repo; setup.sh skips it then.
        if on_droplet -- test -d ocr-example-docs/.git 2>/dev/null; then
            return
        fi
        read -rsp "GitHub token for sil-car/ocr-example-docs: " OCR_PAT
        echo
    fi
}

run_setup() {
    get_pat
    info "Running setup on $ip (takes several minutes)"
    # The token goes over stdin, so it isn't on any command line or in the
    # droplet's metadata.
    local remote_setup
    remote_setup="$(cat <<'EOF'
set -e
read -r OCR_PAT || true
export OCR_PAT
export DEBIAN_FRONTEND=noninteractive
repo_url="$1"
branch="$2"
cd "$HOME"
# Wait for first-boot tasks (cloud-init, unattended upgrades) to release apt.
cloud-init status --wait >/dev/null 2>&1 || true
echo 'DPkg::Lock::Timeout "600";' > /etc/apt/apt.conf.d/99ocr-lock-timeout
# Accept the MS core fonts EULA ahead of setup.sh.
echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections
apt-get update -q
apt-get install -y -q git rsync
if [[ ! -d ocr/.git ]]; then
    git clone --depth=1 ${branch:+--branch "$branch"} "$repo_url" ocr
fi
bash ./ocr/scripts/setup.sh </dev/null
EOF
)"
    on_droplet -- "bash -c $(printf '%q' "$remote_setup") setup $(printf '%q ' "$OCR_REPO_URL" "$OCR_BRANCH")" <<<"$OCR_PAT" \
        || die "setup failed; fix it, then rerun: $0 setup"
    info "Setup done."
}

### Commands.

case "$cmd" in
    up)
        OPTIND=1
        while getopts ":s:r:b:" opt; do
            case $opt in
                s) DO_SIZE="$OPTARG" ;;
                r) DO_REGION="$OPTARG" ;;
                b) OCR_BRANCH="$OPTARG" ;;
                *) die "usage: $0 up [-s SIZE] [-r REGION] [-b BRANCH]" ;;
            esac
        done
        [[ -z $(droplet_ip) ]] || die "droplet \"$DO_NAME\" already exists ($(droplet_ip))."
        fp="$(ssh_key_fingerprint)" || exit 1
        ensure_firewall
        info "Creating droplet \"$DO_NAME\" ($DO_SIZE, $DO_REGION, $DO_IMAGE)"
        doctl compute droplet create "$DO_NAME" \
            --image "$DO_IMAGE" \
            --size "$DO_SIZE" \
            --region "$DO_REGION" \
            --ssh-keys "$fp" \
            --tag-name "$tag" \
            --wait \
            --format Name,PublicIPv4,Memory,VCPUs,Disk \
            || die "couldn't create the droplet."
        require_ip
        wait_for_ssh
        run_setup
        echo
        name_opt=; [[ $DO_NAME != ocr-train ]] && name_opt=" -N $DO_NAME"
        echo "Ready. Start training with: $0${name_opt} train -n 100000"
        ;;

    setup)
        require_ip
        run_setup
        ;;

    train)
        require_ip
        # Quote each argument for the remote shell.
        args="$(printf ' %q' "$@")"
        on_droplet -- "bash ~/ocr/scripts/train.sh -d${args}" || exit 1
        echo "Follow it with: $0 status   or   $0 attach"
        ;;

    status)
        require_ip
        on_droplet -- bash -s <<'EOF'
if screen -ls 2>/dev/null | grep -q '\.ocr-train[[:space:]]'; then
    if pgrep -x lstmtraining >/dev/null; then
        echo "Training: running"
    elif pgrep -f generate-training-data.py >/dev/null; then
        echo "Training: generating images"
    else
        echo "Training: screen session open, but nothing running (finished or failed)"
    fi
else
    echo "Training: no screen session"
fi
log="$(ls -1t ~/tesstrain/data/Latin_afr_*.log 2>/dev/null | head -n1)"
[[ -n $log ]] || exit 0
echo "Log: $log"
echo
grep "New best" "$log" | tail -n1
grep -E "^At iteration" "$log" | tail -n3
grep -E "^(Finished|Training lasted|Error)" "$log" | tail -n3
echo
df -h --output=used,avail,pcent / | tail -n1 | awk '{print "Disk: " $1 " used, " $2 " free (" $3 ")"}'
EOF
        ;;

    attach)
        require_ip
        session="${1:-$screen_name}"
        [[ $session =~ ^[A-Za-z0-9._-]+$ ]] || die "session names may only contain letters, digits, '.', '_' and '-'."
        if [[ $session == "$screen_name" ]]; then
            on_droplet -t -- screen -r "$screen_name"
        else
            # Reattach (taking it over from any other terminal) or create it.
            on_droplet -t -- "if screen -ls | grep -q '\\.${session}[[:space:]]'; then screen -d -r '${session}'; else screen -S '${session}'; fi"
        fi
        ;;

    fetch)
        require_ip
        need rsync
        dest="${RESULTS_DIR}/${DO_NAME}"
        mkdir -p "$dest"
        info "Fetching results to $dest"
        # Skip what can be rebuilt or downloaded again.
        rsync -aPv \
            -e "ssh ${ssh_opts[*]}" \
            --exclude 'langdata/' \
            --exclude 'Latin/' \
            --exclude 'start-*/' \
            --exclude 'all-lstmf' \
            --exclude 'all-gt' \
            --exclude "*checkpoint*" \
            --exclude "*.traineddata" \
            "root@${ip}:tesstrain/data/" "${dest}/"
        ;;

    down)
        OPTIND=1
        no_fetch=
        yes=
        while getopts ":ny" opt; do
            case $opt in
                n) no_fetch=YES ;;
                y) yes=YES ;;
                *) die "usage: $0 down [-n] [-y]" ;;
            esac
        done
        require_ip
        if [[ -z $yes ]] && on_droplet -- pgrep -x lstmtraining >/dev/null 2>&1; then
            read -rp "Training is still running on $DO_NAME. Destroy it anyway? [y/N] " a
            [[ $a == [yY]* ]] || exit 1
        fi
        if [[ -z $no_fetch ]]; then
            "$0" -N "$DO_NAME" fetch || die "fetch failed; droplet kept. Use -n to skip fetching."
        fi
        if [[ -z $yes ]]; then
            read -rp "Destroy droplet \"$DO_NAME\" ($ip)? [y/N] " a
            [[ $a == [yY]* ]] || exit 1
        fi
        info "Destroying droplet \"$DO_NAME\""
        doctl compute droplet delete --force "$DO_NAME"
        ssh-keygen -R "$ip" -f "$known_hosts" >/dev/null 2>&1
        ;;

    list)
        doctl compute droplet list --tag-name "$tag" --format Name,PublicIPv4,Memory,VCPUs,Region,Status
        ;;

    update)
        require_ip
        on_droplet -- git -C ocr pull --ff-only
        ;;

    sync)
        require_ip
        need rsync
        info "Copying ${local_repo}/scripts/ to the droplet"
        rsync -av -e "ssh ${ssh_opts[*]}" "${local_repo}/scripts/" "root@${ip}:ocr/scripts/"
        ;;

    ssh)
        require_ip
        if [[ $# -gt 0 ]]; then
            on_droplet -- "$@"
        else
            on_droplet -t --
        fi
        ;;

    ip)
        require_ip
        echo "$ip"
        ;;

    *)
        echo "$usage"
        exit 1
        ;;
esac
