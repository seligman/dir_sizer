## Todo

Tracking the work items to get to different stages of development.

Items needed to get past an alpha release:

- [x] Fix issue with too-nested layout
- [x] Add labels for top level rects
- [x] Add a local file system abstraction.
- [x] Move the "cache" logic out of the S3 abstraction
- [ ] Improve comments
- [ ] Add a requirements.txt file to bring in all needed packages
- [ ] Test, test, test
- [x] If an abstraction is missing a necessary package, hide it
- [x] Add more details to the webpage to show overview, etc
- [ ] Some way of parsing AWS Inventory Reports for larger buckets

Wish list items in a future version:

- [x] Add or extend the S3 abstraction to show all buckets in one pass
- [ ] Add a "cost" size option to S3 to size the bucket by costs
- [ ] Add a SSH abstraction
- [ ] Add a Google Storage abstraction
- [ ] Add an Azure Blob abstraction
- [ ] Add a FTP abstraction
- [ ] A local view of some sort
- [ ] Options to control the main size in the HTML view 
- [ ] Some level of integration with CloudWatch as a widget
- [ ] An example Lambd that auto-generates a webpage with some frequency
