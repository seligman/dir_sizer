#!/usr/bin/env python3

# This is a thin wrapper around AWS APIs that return a page from a larger set, and 
# return a continuation token to get the next page.  It offers a slightly cleaner
# interface than botocore's 'get_paginator', but more importantly, it worse with
# any API that follows this pattern, not just APIs that have a specific 
# paginator available.
#
# To call it, just call a method like:
# 
# for _, cur in aws_pager(s3, 'list_objects_v2', 'Contents', Bucket='example-bucket'):
#     print(cur['Key'])
#
# Which is equivalent to the following pattern:
#
# paginator = s3.get_paginator('list_objects_v2')
# for page in paginator.paginate(Bucket='scotts-mess'):
#     for cur in page.get('Contents', []):
#         print(cur['Key'])

# Returns an enumeration of all results from all pages as a tuple
# where the first item is the result from results, and the second
# item in the tuple is the result
#
# client is the boto client object to call into
# function is a string defining the function to call in client
# results is either a string of the single result type to look
# for in each page, or a tuple or list of each results to look
# for in each page
# args and kwargs are the options to pass along to function
def aws_pager(client, function, results, *args, **kwargs):
    # Get a function to call
    function = getattr(client, function)

    # If we're passed in a single result type, turn it into a tuple
    # of one element.
    if not isinstance(results, (list, tuple)):
        results = (results,)
    
    # Loop through each page
    while True:
        resp = function(*args, **kwargs)
        for result in results:
            for cur in resp.get(result, []):
                yield result, cur
            
        if 'NextContinuationToken' in resp:
            # Use the ContinuationToken format
            kwargs['ContinuationToken'] = resp['NextContinuationToken']
        elif 'NextToken' in resp:
            # Use the NextToken format
            kwargs['NextToken'] = resp['NextToken']
        else:
            break

if __name__ == "__main__":
    print("This module is not meant to be called directly.")
