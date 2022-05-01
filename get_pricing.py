#!/usr/bin/env python3

from datetime import datetime
from urllib.request import urlopen
import json
import os

def get_pricing(save_data_filename=None):
    # These JSON objects are used by the AWS S3 Pricing Page at
    # https://aws.amazon.com/s3/pricing/
    urls = {
        "costs": "https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/s3/USD/current/s3.json",
        "deep": "https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/s3glacierdeeparchive/USD/current/s3glacierdeeparchive.json",
    }    

    # The final data to save
    final = {"_meta": {"data downloaded": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}}

    # Load the data for each URL in turn
    for key in urls:
        urls[key] = json.load(urlopen(urls[key]))
        final["_meta"][key + " updated"] = urls[key]["manifest"]["hawkFilePublicationDate"]

    # Get all of the regions, since these JSON files from AWS drive user-visible 
    # data, all of the regions are the full English description of the region.
    regions = [x for x in urls['costs']['regions'] if len(x)]

    # A lookup table for the regions to normal ID
    region_ids = {
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

    # Make sure the lookup table is consistent
    temp = set()
    for region_id in region_ids.values():
        if region_id in temp:
            raise Exception("Region ID " + region_id + " is used more than once!")
        temp.add(region_id)
    for region_name in regions:
        if region_name not in region_ids:
            raise Exception(region_name + " is not a known region!")

    for region in regions:
        # Pull out the data for this region
        temp = {}
        final[region_ids[region]] = temp

        # Pull out the costs from each field in turn
        temp['Standard'] = urls['costs']['regions'][region]['Standard Storage Over 500 TB per GB Mo']['price']
        temp['StandardIA'] = urls['costs']['regions'][region]['Standard Infrequent Access Storage per GB-Mo']['price']
        temp['StandardIA-OneAZ'] = urls['costs']['regions'][region]['One Zone Infrequent Access Storage Inf per GB-Mo']['price']
        temp['Glacier'] = urls['costs']['regions'][region]['Glacier Storage per GB Mo']['price']
        temp['GlacierInstant'] = urls['costs']['regions'][region]['Glacier Instant Retrieval Storage']['price']
        temp['DeepArchive'] = urls['deep']['regions'][region]['Glacier Deep Archive GB Mo']['price']

        # Clean up the output a bit
        for key in temp:
            temp[key] = temp[key].rstrip("0")

    if save_data_filename is not None:
        # Create a sanitized version we can compare to a previous run
        temp = final["_meta"]["data downloaded"]
        final["_meta"]["data downloaded"] = ""
        updated_data = json.dumps(final, sort_keys=True)
        final["_meta"]["data downloaded"] = temp

        # Load the old version if it's available
        old_data = ""
        if os.path.isfile(save_data_filename):
            with open(save_data_filename, "rt", encoding="utf-8") as f:
                old_data = json.load(f)
                old_data["_meta"]["data downloaded"] = ""
                old_data = json.dumps(old_data, sort_keys=True)

        if old_data == updated_data:
            print("The pricing data in " + save_data_filename + " has not changed")
        else:
            # Dump out the data
            with open(save_data_filename, "wt", newline="\n", encoding="utf-8") as f:
                json.dump(final, f, indent=4, sort_keys=True)
                f.write("\n")

            print("All done, created " + save_data_filename)

    return final

if __name__ == "__main__":
    get_pricing(save_data_filename="s3_pricing_data.json")
