from flask import Flask, g, request, render_template, redirect
import os
from rdflib.plugins.stores.sparqlstore import SPARQLUpdateStore, SPARQLStore
from collections import namedtuple


Config = namedtuple("Config", ["PORT", "SPARQL_QUERY", "SPARQL_UPDATE"])
Review = namedtuple(
    "Review", 
    [ "uri", "pubdate", "album", "reviewer", "rating" ]
)
Album = namedtuple("Album", ["uri", "artist", "title"])
Reviewer = namedtuple("Reviewer", ["uri", "name"])
Rating = namedtuple("Rating", ["normalizedScore"])
