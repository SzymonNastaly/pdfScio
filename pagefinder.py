import json
import unicodedata
import itertools
"""TODO: Understand difference between NFC and NFKC forms in unicodedata"""
"""TODO: Testing with multiple statements (of other companies)"""
"""TODO: Rename everything thats necessary (in accordance to pep8)"""
"""TODO: Necessary methods: 
check if konzernabschluss or jahresabschluss,
allocate pages to statements,
verificator of pages (if every statement has pagenumbers),
"""


def search_term(pages, term):
    """Searches for term in all pages"""
    pagenumbers = []
    for index, pagetext in enumerate(pages):
        if term.lower() in unicodedata.normalize("NFC", pagetext.lower()):
            pagenumbers.append(index+1)
    return pagenumbers


def file_to_pagelist(filepath):
    """Reads text file, creates list, inserts each page into a list item"""
    with open(filepath, "r") as file:
        pdftext = file.read()
        pages = pdftext.split(sep="-/l/-")
        pages.pop(0)
        return pages


def json_to_list(filepath, language):
    """Parses all key_figure-words in all json fields into one list"""
    with open(filepath, "r") as file:
        terms_overview_file = file.read()
        terms_overview = json.loads(terms_overview_file)
        terms = {}
        for statement in list(terms_overview['key_figures']):
            terms[statement] = {}
            for figure in list(terms_overview['key_figures'][statement]):
                terms_of_figure = terms_overview['key_figures'][statement][figure][language]
                terms[statement][figure] = terms_of_figure
        return terms


def find_page_occurences(terms, pages):
    """Finds all page numbers for all terms"""
    pages_with_figure = {}
    for statement in terms:
        pages_with_figure[statement] = {}
        for figure in terms[statement]:
            terms_of_figure = terms[statement][figure]
            pages_with_figure[statement][figure] = set()
            for term in terms_of_figure:
                pagesoccurences = search_term(pages, term)
                for page in pagesoccurences:
                    pages_with_figure[statement][figure].add(page)
    return pages_with_figure


def has_counter(pagenumber, statement, occurenceCounter):
    """Checks if a page number already has a counter in the occurenceCounter"""
    if pagenumber in occurenceCounter[statement].keys():
        return True
    else:
        return False

def count_page_occurences(pages_with_figure):
    """Counts how often each page was found for the different key_figures in
    pages_with_figure. i.e. if the terms for revenue and ebit were found on p62, its
    counter is 2.
    """
    occurenceCounter = {}
    for statement in pages_with_figure:
        occurenceCounter[statement] = {}
        for key_figure in pages_with_figure[statement]:
            for pagenumber in pages_with_figure[statement][key_figure]:
                if has_counter(pagenumber, statement, occurenceCounter):
                    occurenceCounter[statement][pagenumber] += 1
                else:
                    occurenceCounter[statement][pagenumber] = 1
    return occurenceCounter


def find_max_count_pages(occurenceCounter):
    """Selects the most common page(s) for a statement. They are
    selected by the highest count numbers. i.e. if on p62 2 key_figures were
    found, but on other pages only one, the highOccurencePage is 62.
    """
    maxCountPages = {}
    for statement in occurenceCounter:
        maxCountPages[statement] = []
        if occurenceCounter[statement] != {}:
            maxPageCount = max(occurenceCounter[statement].values())
            for page in occurenceCounter[statement]:
                if occurenceCounter[statement][page] == maxPageCount:
                    maxCountPages[statement].append(page)
    return maxCountPages


def calculate_difference(triple):
    """Calculates the highest difference existent in the given page numbers.
    Used in eliminate_not_nearby().
    """
    pairs = itertools.combinations(triple, 2)
    highestDifference = 0
    for pair in pairs:
        difference = abs(pair[0] - pair[1])
        if difference > highestDifference:
            highestDifference = difference
    return highestDifference


def eliminate_not_nearby(maxCountPages):
    """Eliminates pages that can't be correct, simply because of their
    'distance' to the other ones. i.e. if balance sheet is p34,
    cashflow statement p36, than p62 can't be anything.
    """
    MAX_DIFFERENCE = 5  # magic number! -> other way?
    pagenumbers = []
    for statement in maxCountPages:
        pagenumbers.append(maxCountPages[statement])
    triples = list(itertools.product(*pagenumbers))
    nearbypages = triples.copy()
    for triple in triples:
        highestdifference = calculate_difference(triple)
        if highestdifference > MAX_DIFFERENCE:
            nearbypages.remove(triple)
    return nearbypages


def select_correct_pages(pages_with_figure):
    """Selects pages from all pages with high numbers of key_figures found, on
    which statements probably are.
    """
    print(None)


def find_statement_pages(filepath, termsfile, language):
    """Finds page numbers of financial statements in annual report txt-file
    (TODO: PDF file)
    (TODO: un-hardcode filepaths, etc.)
    """
    pages = file_to_pagelist(filepath)
    terms = json_to_list(termsfile, language)
    pages_with_figure = find_page_occurences(terms, pages)
    occurenceCounter = count_page_occurences(pages_with_figure)
    maxCountPages = find_max_count_pages(occurenceCounter)
    nearbypages = eliminate_not_nearby(maxCountPages)

    return nearbypages
