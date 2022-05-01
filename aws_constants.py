#!/usr/bin/env python3

# Some useful AWS Metadata

# A lookup table for the regions to normal AWS Region ID
REGION_IDS = {
    "Africa (Cape Town)": "af-south-1",
    "Asia Pacific (Hong Kong)": "ap-east-1",
    "Asia Pacific (Jakarta)": "ap-southeast-3",
    "Asia Pacific (Mumbai)": "ap-south-1",
    "Asia Pacific (Osaka)": "ap-northeast-3",
    "Asia Pacific (Seoul)": "ap-northeast-2",
    "Asia Pacific (Singapore)": "ap-southeast-1",
    "Asia Pacific (Sydney)": "ap-southeast-2",
    "Asia Pacific (Tokyo)": "ap-northeast-1",
    "AWS GovCloud (US-East)": "us-gov-east-1",
    "AWS GovCloud (US)": "us-gov-west-1",
    "Canada (Central)": "ca-central-1",
    "EU (Frankfurt)": "eu-central-1",
    "EU (Ireland)": "eu-west-1",
    "EU (London)": "eu-west-2",
    "EU (Milan)": "eu-south-1",
    "EU (Paris)": "eu-west-3",
    "EU (Stockholm)": "eu-north-1",
    "Middle East (Bahrain)": "me-south-1",
    "South America (Sao Paulo)": "sa-east-1",
    "US East (N. Virginia)": "us-east-1",
    "US East (Ohio)": "us-east-2",
    "US West (N. California)": "us-west-1",
    "US West (Oregon)": "us-west-2",
}

# Different types of S3 storages, and where the costs come from
#   "desc"        = The local description/key for the storage class
#   "page_source" = The AWS source for this data
#   "page_desc"   = The key in page_source for this value
#   "cw"          = The cloudwatch metric for this value
#   "s3"          = The S3 storage class for this type (may be None)
S3_COST_CLASSES = [
    {
        'desc': 'DeepArchive', 
        'page_source': 'deep', 'page_desc': 'Glacier Deep Archive GB Mo', 
        'cw': 'DeepArchiveStorage',
        's3': 'DEEP_ARCHIVE',
    },
    {
        'desc': 'Glacier', 
        'page_source': 'costs', 'page_desc': 'Glacier Storage per GB Mo', 
        'cw': 'GlacierStorage',
        's3': 'GLACIER',
    },
    {
        'desc': 'GlacierInstant', 
        'page_source': 'costs', 'page_desc': 'Glacier Instant Retrieval Storage', 
        'cw': 'GlacierInstantRetrievalStorage',
        's3': 'GLACIER_IR',
    },
    {
        'desc': 'IntelligentAA', 
        'page_source': 'costs', 'page_desc': 'IntelligentTieringArchiveStorage', 
        'cw': 'IntelligentTieringAAStorage',
        's3': None,
    },
    {
        'desc': 'IntelligentAIA', 
        'page_source': 'costs', 'page_desc': 'IntelligentTieringArchiveInstantAccess', 
        'cw': 'IntelligentTieringAIAStorage',
        's3': 'INTELLIGENT_TIERING',
    },
    {
        'desc': 'IntelligentDAA', 
        'page_source': 'costs', 'page_desc': 'IntelligentTieringDeepArchiveStorage', 
        'cw': 'IntelligentTieringDAAStorage',
        's3': None,
    },
    {
        'desc': 'IntelligentFA', 
        'page_source': 'costs', 'page_desc': 'Intelligent Tiering Frequent Access Over 500 TB per GB Mo', 
        'cw': 'IntelligentTieringFAStorage',
        's3': None,
    },
    {
        'desc': 'IntelligentIA', 
        'page_source': 'costs', 'page_desc': 'Intelligent Tiering Infrequent Access per GB Mo', 
        'cw': 'IntelligentTieringIAStorage',
        's3': None,
    },
    {
        'desc': 'ReducedRedundancy', 
        'page_source': 'costs', 'page_desc': 'Reduced Redundancy Storage Over 5 000 TB per GB Mo', 
        'cw': 'ReducedRedundancyStorage',
        's3': 'REDUCED_REDUNDANCY',
    },
    {
        'desc': 'Standard', 
        'page_source': 'costs', 'page_desc': 'Standard Storage Over 500 TB per GB Mo', 
        'cw': 'StandardStorage',
        's3': 'STANDARD',
    },
    {
        'desc': 'StandardIA', 
        'page_source': 'costs', 'page_desc': 'Standard Infrequent Access Storage per GB-Mo', 
        'cw': 'StandardIAStorage',
        's3': 'STANDARD_IA',
    },
    {
        'desc': 'StandardIA-OneAZ', 
        'page_source': 'costs', 'page_desc': 'One Zone Infrequent Access Storage Inf per GB-Mo', 
        'cw': 'OneZoneIAStorage',
        's3': 'ONEZONE_IA',
    },
]

if __name__ == "__main__":
    print("This module is not meant to be run directly")
