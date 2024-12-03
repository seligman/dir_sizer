#!/usr/bin/env python3

from datetime import datetime
from urllib.request import urlopen
from aws_pager import aws_pager # type: ignore
import boto3
import gzip
import json
import os
import sys
if sys.version_info >= (3, 11): from datetime import UTC
else: import datetime as datetime_fix; UTC=datetime_fix.timezone.utc

DEBUG_REQUESTS = False

def msg(value, temp=False):
    # Helper to show a message, including temporary status messages
    if 'last' not in msg.__dict__:
        msg.last = ""
    if len(msg.last) > 0:
        if len(msg.last) > len(value):
            extra = len(msg.last) - len(value)
            to_show = "\b" * extra + " " * extra + "\r" + value
        else:
            to_show = "\r" + value
    else:
        to_show = value
    if temp:
        print(to_show, end="", flush=True)
        msg.last = value
    else:
        print(to_show, flush=True)
        msg.last = ""

def cache_json(desc, final, save_data_filename):
    if save_data_filename is None:
        return

    def serialize_for_compare(data):
        # Force a deep copy by serialize/unserializing
        data = json.loads(json.dumps(data))
        # Ignore the _meta key when comparing
        data["_meta"] = "-iognore-"
        # Serialize to a set format
        data = json.dumps(data, sort_keys=True)
        return data

    updated_data = serialize_for_compare(final)

    # Load the old version if it's available
    old_data = ""
    if os.path.isfile(save_data_filename):
        with open(save_data_filename, "rt", encoding="utf-8") as f:
            old_data = json.load(f)
            old_data = serialize_for_compare(old_data)

    if old_data == updated_data:
        msg("The " + desc + " in " + save_data_filename + " has not changed.")
    else:
        # Dump out the data
        with open(save_data_filename, "wt", newline="\n", encoding="utf-8") as f:
            json.dump(final, f, indent=4, sort_keys=True)
            f.write("\n")
        msg("All done, created " + save_data_filename + " for " + desc)


def get_regions(save_data_filename=None):
    ssm = boto3.client('ssm', region_name="us-east-1")

    # The final data to save
    final = {"_meta": {
        "_comment": "This file is generated by " + os.path.split(__file__)[-1] + ", run that script to update it automatically.",
        "data downloaded": datetime.now(UTC).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%SZ",
    )}}

    final["regions"] = {}

    msg("Loading regions from boto3...", temp=True)

    for i, (_, parameter) in enumerate(aws_pager(ssm, 'get_parameters_by_path', 'Parameters', Path="/aws/service/global-infrastructure/regions")):
        region = parameter['Name'].split("/")[-1]
        msg(f"Loading region #{i+1},'{region}' from boto3...", temp=True)
        details = ssm.get_parameter(Name=f"/aws/service/global-infrastructure/regions/{region}/longName")
        desc = details["Parameter"]["Value"]
        final["regions"][region] = desc

    cache_json("region data", final, save_data_filename)

    return final

def get_pricing(save_data_filename=None):
    # These JSON objects are used by the AWS S3 Pricing Page at
    # https://aws.amazon.com/s3/pricing/
    urls = {
        "costs": "https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/s3/USD/current/s3.json",
        "deep": "https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/s3glacierdeeparchive/USD/current/s3glacierdeeparchive.json",
    }    

    # The final data to save
    final = {"_meta": {
        "_comment": "This file is generated by " + os.path.split(__file__)[-1] + ", run that script to update it automatically.",
        "data downloaded": datetime.now(UTC).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%SZ",
    )}}

    # Load the data for each URL in turn
    for key in urls:
        msg(f"Getting {key} pricing data...", temp=True)
        resp = urlopen(urls[key])
        resp_data = resp.read()
        if resp.headers.get("Content-Encoding", "") == "gzip":
            resp_data = gzip.decompress(resp_data)
        # Helper code to debug the responses from the different URLs
        if DEBUG_REQUESTS:
            debug_i = 0
            while True:
                debug_fn = f"debug_{debug_i:04d}.dat"
                if not os.path.isfile(debug_fn):
                    break
                debug_i += 1
            with open(debug_fn, "wb") as debug_f:
                debug_f.write(f"URL: {urls[key]}".encode("utf-8"))
                debug_f.write(f"Length: {len(resp_data)}\n".encode("utf-8"))
                debug_f.write(f"Headers:\n".encode("utf-8"))
                for debug_key, debug_value in resp.headers.items():
                    debug_f.write(f"  {debug_key}: {debug_value}\n".encode("utf-8"))
                debug_f.write(f"Data:\n".encode("utf-8"))
                debug_f.write(resp_data)
        urls[key] = json.loads(resp_data)
        final["_meta"][key + " updated"] = urls[key]["manifest"]["hawkFilePublicationDate"]

    # Get all of the regions, since these JSON files from AWS drive user-visible 
    # data, all of the regions are the full English description of the region.
    regions = [x for x in urls['costs']['regions'] if len(x)]
    # Ignore some artifacts of how the page is created
    regions = [x for x in regions if x not in {"Any"}]

    # Load the region names, and handle the edge cases with slightly different names
    with open("s3_regions.json") as f:
        all_regions = json.load(f)
        all_regions = {y: x for x, y in all_regions["regions"].items()}
        # This is both 'AWS GovCloud (US-East)' and 'AWS GovCloud (US)'
        all_regions["AWS GovCloud (US)"] = "us-gov-west-1"
        # The "Europe" regions are also "EU" regions
        for region_name in [x for x in all_regions if x.startswith("Europe")]:
            all_regions[region_name.replace("Europe ", "EU ")] = all_regions[region_name]

    # Raise an exception if there's a not yet known region
    for region_name in regions:
        if region_name not in all_regions:
            raise Exception(region_name + " is not a known region!")

    for region in regions:
        # Pull out the data for this region
        temp = {}
        final[all_regions[region]] = temp

        with open("s3_cost_classes.json") as f:
            s3_cost_classes = json.load(f)

        # Pull out the costs from each field in turn
        for s3_cost in s3_cost_classes['classes']:
            if region in urls[s3_cost['page_source']]['regions']:
                # The page description can be a list for cases where are multiple possibilites
                page_descs = s3_cost['page_desc']
                if isinstance(page_descs, str):
                    page_descs = [page_descs]
                found_item = False
                for page_desc in page_descs:
                    if page_desc in urls[s3_cost['page_source']]['regions'][region]:
                        temp[s3_cost['desc']] = urls[s3_cost['page_source']]['regions'][region][page_desc]['price']
                        found_item = True
                        break
                if not found_item:
                    raise Exception("Unable to find: " + str(page_descs) + ", for " + str(s3_cost))
                temp[s3_cost['desc']] = temp[s3_cost['desc']].rstrip('0')
            else:
                print(f"\nWARNING: {s3_cost} not found in {region}", flush=True)
                temp[s3_cost['desc']] = "0.00"

    cache_json("pricing data", final, save_data_filename)

    return final

if __name__ == "__main__":
    get_regions(save_data_filename="s3_regions.json")
    get_pricing(save_data_filename="s3_pricing_data.json")
