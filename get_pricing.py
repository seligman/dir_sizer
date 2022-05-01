#!/usr/bin/env python3

from aws_constants import REGION_IDS, S3_COST_CLASSES
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

    # Raise an exception if there's a not yet known region
    for region_name in regions:
        if region_name not in REGION_IDS:
            raise Exception(region_name + " is not a known region!")

    for region in regions:
        # Pull out the data for this region
        temp = {}
        final[REGION_IDS[region]] = temp

        # Pull out the costs from each field in turn
        for s3_cost in S3_COST_CLASSES:
            temp[s3_cost['desc']] = urls[s3_cost['page_source']]['regions'][region][s3_cost['page_desc']]['price']
            temp[s3_cost['desc']] = temp[s3_cost['desc']].rstrip('0')

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
