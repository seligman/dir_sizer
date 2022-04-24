# Dir Sizer

This is a *work in progress*.

This is a utility to visualize the size of a directory, or a directory like thing.  Right now it produces webpages that look like this:

![](images/example_view.png)

Showing the relative size of folders, making it easy to see what areas of a folder are using the most space.

Right now it only supports producing reports for AWS S3 Buckets, but in the future it will add support for other sources, including the local file system, Google Storage Bucket, Azure Blobs, remote filesystems via SSH, and perhaps others.

To run it, right now you'll need a recent version of Python installed, along with the boto3 package available.  Then you can run a command like:

```
python dir_sizer --s3 --bucket example-bucket --output example.html
```

Which will produce a file called "example.html" showing details of the "example-bucket" AWS S3 Bucket.

You can track the current [outstanding work items](TODO.md).  Questions? Feedback? [E-mail me](mailto:scott.seligman@gmail.com).
