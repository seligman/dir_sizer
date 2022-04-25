# Dir Sizer

This is a *work in progress*, right now consider this an Alpha or Proof of Concept level.

`dir_sizer` is a utility to visualize the size of a directory, or a directory like thing.  Right now it produces webpages that look like this:

![](images/example_view.png)

Showing the relative size of folders, making it easy to see what areas of a folder are using the most space.

It supports scanning and producing reports for AWS S3 Buckets and directories in the local file system.  In the future it will add support for other sources, including Google Storage Bucket, Azure Blobs, remote filesystems via SSH, and perhaps others.

To run it, right now you'll need a recent version of Python installed, along with the boto3 package available.  Then you can run a command like:

```
python dir_sizer.py --s3 --bucket example-bucket --output example.html
```

Which will produce a file called "example.html" showing details of the "example-bucket" AWS S3 Bucket.

You can track the current [outstanding work items](TODO.md).  Questions? Feedback? [E-mail me](mailto:scott.seligman@gmail.com).
