# Training

There are several factors considered when preparing and running the training:
- character generation type (random or weighted)
- over-generation for characters getting poor results
- image line length (in characters)
- image height (in pixels)
- number of images generated
- number of training iterations run
- type of training (fine tuning or layer replacement)

Each factor has been seen to influence the performance of the finished model, so more than two dozen models have been produced in order to compare the relative importance of each factor.
*However*, not all factors have been tested in complete isolation, so there is no quantification of the importance of each factor. If changing a factor improved the resulting model, then that change was kept without first testing if a different change would have improved the model even more.
