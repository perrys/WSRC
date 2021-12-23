#!/usr/bin/python

def dotted_lookup(record, name):
    for tok in name.split("."):
        item = record = getattr(record, tok)
        if hasattr(item, "__call__"):
            item = record = item()
        if item is None:
            break
    return item

