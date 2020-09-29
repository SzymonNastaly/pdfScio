import json
import unicodedata
import itertools
import os
from datetime import date
import logging
import logging.config

from pdfminer.high_level import extract_text

#TODO: Understand difference between NFC and NFKC forms in unicodedata
#TODO: Testing with multiple statements (of other companies)
#TODO: general change - add count for each term, not for each topic
#TODO: method - check if konzernabschluss or jahresabschluss
#TODO: method - allocate pages to statements
#TODO: method - verificator of pages (if every statement has pagenumbers)
#TODO tests

logging.config.fileConfig('logging.conf')
logger = logging.getLogger('root.pagefinder')
logger.info('started')


class Pdf:
    def __init__(self, path):
        self.path = path
        logger.info('pdf initialized path {}'.format(self.path))

    def create_textfile(self):
        pages = []

        for page in range(1000):
            page = [
                page,
            ]
            text = extract_text(self.path, page_numbers=page)
            if text:
                pages.append(text)
                logger.debug('pdf append page {}'.format(page))
            else:
                logger.info('pdf {} ready'.format(self.path))
                break

        filename = self.path.split('/')[2][:-4]
        textfilepath = "export/{}.txt".format(filename)
        logger.debug('textfile at {}'.format(textfilepath))

        with open(textfilepath, "a") as file:
            for index, page in enumerate(pages):
                file.write("\n-/l/-")
                file.write(page)
            logger.info('textfile {} exported'.format(filename))

        return textfilepath


class Statement:
    def __init__(self, path, termsfile, language):
        self.path = path
        self.termsfile = termsfile
        self.language = language
        logger.info('statement {} initialized'.format(self.path))

    def file_to_pagelist(self):
        """Reads text file, creates list, inserts each page into a list item"""
        try:
            logger.debug('trying utf-8')
            with open(self.path, "r", encoding="utf-8") as file:
                logger.debug('textfile {} opened'.format(self.path))
                pdftext = file.read()
                pages = pdftext.split(sep="-/l/-")
                pages.pop(0)
                logger.info('statement {} read into memory'.format(self.path))
                return pages
        except:
            logger.warning('not utf-8')

        try:
            logger.debug('trying utf-16')
            with open(self.path, "r", encoding="utf-16") as file:
                logger.debug('textfile {} opened'.format(self.path))
                pdftext = file.read()
                pages = pdftext.split(sep="-/l/-")
                pages.pop(0)
                logger.info('statement {} read into memory'.format(self.path))
                return pages
        except:
            logger.warning('trying utf-16')

    def json_to_list(self):
        """Parses all key_figure-words in all json fields into one list"""
        logger.debug('parsing termsfile {} to json'.format(self.termsfile))
        with open(self.termsfile, "r") as file:
            logger.debug('termsfile {} opened'.format(self.termsfile))
            terms_overview_file = file.read()
            terms_overview = json.loads(terms_overview_file)
            terms = {}
            for statement in list(terms_overview["key_figures"]):
                terms[statement] = {}
                for figure in list(terms_overview["key_figures"][statement]):
                    terms_of_figure = terms_overview["key_figures"][statement][figure][
                        self.language
                    ]
                    terms[statement][figure] = terms_of_figure
            logger.info('termsfile {} read into memory'.format(self.termsfile))
            return terms

    def search_term(self, pages, term):
        """Searches for term in all pages"""
        logger.info('searching for {}'.format(term))
        pagenumbers = []
        for index, pagetext in enumerate(pages):
            if term.lower() in unicodedata.normalize("NFC", pagetext.lower()):
                pagenumbers.append(index + 1)
                logger.debug('{} found on page {}'.format(term, index+1))
        logger.debug('statement {} term:{} on pages:{}'.format(self.path,term,pagenumbers))
        logger.info('search for {} ready'.format(term))
        return pagenumbers

    def find_pages_with_terms(self, terms, pages):
        """Finds all relevant pages (pages at which at least one term is found)"""
        logger.info('finding page occurences')
        pages_with_figure = {}
        for statement in terms:
            pages_with_figure[statement] = {}
            for figure in terms[statement]:
                terms_of_figure = terms[statement][figure]
                # pages_with_figure[statement][figure] = set()
                pages_with_figure[statement][figure] = {}
                for term in terms_of_figure:
                    pages_with_figure[statement][figure][term] = set()
                    pagesoccurences = self.search_term(pages, term)
                    for page in pagesoccurences:
                        logger.debug('adding page {} for figure {}'.format(page, figure))
                        pages_with_figure[statement][figure][term].add(page)
        logger.debug('pages found: {}'.format(pages_with_figure))
        logger.info('returning pages_with_figure')
        return pages_with_figure

    def has_counter(self, pagenumber, statement, occurenceCounter):
        """Checks if a page number already has a counter in the occurenceCounter"""
        if pagenumber in occurenceCounter[statement].keys():
            logger.debug('pagenumber {} has counter'.format(pagenumber))
            return True
        else:
            logger.debug('pagenumber {} no counter'.format(pagenumber))
            return False

    def count_page_occurences(self, pages_with_figure):
        """Counts how often each page was found for the different key_figures in
        find_pages_with_terms. i.e. if the terms for revenue and ebit were found on p62, its
        counter is 2.
        """
        logger.info('counting page occurences for statement {}'.format(self.path))
        occurenceCounter = {}
        for statement in pages_with_figure:
            occurenceCounter[statement] = {}
            for key_figure in pages_with_figure[statement]:
                for term in pages_with_figure[statement][key_figure]:
                    logger.debug('getting numbers from key_figure {} term {}'.format(key_figure, term))
                    for pagenumber in pages_with_figure[statement][key_figure][term]:
                        if self.has_counter(pagenumber, statement, occurenceCounter):
                            logger.debug('adding one for {}'.format(pagenumber))
                            occurenceCounter[statement][pagenumber] += 1
                        else:
                            logger.debug('setting one for {}'.format(pagenumber))
                            occurenceCounter[statement][pagenumber] = 1
            logger.debug('{} - occurenceCounter {}'.format(self.path, occurenceCounter))
        logger.info('returning occurenceCounter')
        return occurenceCounter

    def find_max_count_pages(self, occurenceCounter):
        """Selects the most common page(s) for a statement. They are
        selected by the highest count numbers. i.e. if on p62 2 key_figures were
        found, but on other pages only one, the highOccurencePage is 62.
        """
        logger.info('finding max count pages for {}'.format(self.path))
        maxCountPages = {}
        for statement in occurenceCounter:
            maxCountPages[statement] = []
            balance_pages = 0
            offset = 1
            if occurenceCounter[statement] != {}:
                maxPageCount = max(occurenceCounter[statement].values())
                for page in occurenceCounter[statement]:
                    if occurenceCounter[statement][page] == maxPageCount:
                        maxCountPages[statement].append(page)
                        if statement == 'balance_sheet':
                            balance_pages += 1
        while balance_pages < 2:
            for page in occurenceCounter['balance_sheet']:
                maxPageCount = max(occurenceCounter['balance_sheet'].values())
                if occurenceCounter['balance_sheet'][page] == maxPageCount - offset:
                    print(page)
                    maxCountPages['balance_sheet'].append(page)
                    balance_pages += 1
                    print(maxCountPages)
                    break
            offset += 1


        logger.debug('maxCountPages {}'.format(maxCountPages))
        logger.info('return maxCountPages for {}'.format(self.path))
        return maxCountPages

    def calculate_difference(self, triple):
        """Calculates the highest difference existent in the given page numbers.
        Used in eliminate_not_nearby().
        """
        logger.debug('calculating difference in {}'.format(triple))
        pairs = itertools.combinations(triple, 2)
        highestDifference = 0
        for pair in pairs:
            difference = abs(pair[0] - pair[1])
            if difference > highestDifference:
                highestDifference = difference
        logger.debug('difference for {} is {}'.format(triple, highestDifference))
        logger.info('returning highestDifference for {}'.format(self.path))
        return highestDifference

    def eliminate_not_nearby(self, maxCountPages):
        """Eliminates pages that can't be correct, simply because of their
        'distance' to the other ones. i.e. if balance sheet is p34,
        cashflow statement p36, than p62 can't be anything.
        """
        logger.info('eliminating not nearby')
        logger.info('maxCountPages are {}'.format(maxCountPages))
        MAX_DIFFERENCE = 5
        pagenumbers = []
        for statement in maxCountPages:
            pagenumbers.append(maxCountPages[statement])
        triples = list(itertools.product(*pagenumbers))
        nearbypages = triples.copy()
        for triple in triples:
            highestdifference = self.calculate_difference(triple)
            logger.debug('highestdifference for {} is {}'.format(triple, highestdifference))
            if highestdifference > MAX_DIFFERENCE:
                logger.debug('deleting {} from nearbypages'.format(triple))
                nearbypages.remove(triple)
        logger.debug('returning nearbypages {}'.format(nearbypages))
        logger.info('returning nearbypages for {}'.format(self.path))
        return nearbypages


    def undouble_pages(self, nearbypages):
        """
        It can happen that eliminate_not_nearby() returns multiple touples and/or touples containing the same pagenumber mulitple times.
        i.e.: nearbypages = [(34, 35, 35), (34, 37, 35)] --> there should be only one list, with not doubled pages -> [34,35,37]
        :param nearbypages: pagenumber data from last method ( eliminate_not_nearby() )
        :return: list with undoubled pagenumber data, i.e. [34,35,37]
        """
        undoubled = set()
        for pagegroup in nearbypages:
            for page in pagegroup:
                undoubled.add(page)

        undoubled = list(undoubled)

        return undoubled

    def find_statement_pages(self):
        logger.info('finding statement for {}'.format(self.path))
        pages = self.file_to_pagelist()
        terms = self.json_to_list()
        pages_with_figure = self.find_pages_with_terms(terms, pages)
        occurenceCounter = self.count_page_occurences(pages_with_figure)
        maxCountPages = self.find_max_count_pages(occurenceCounter)
        nearbypages = self.eliminate_not_nearby(maxCountPages)
        undoubled = self.undouble_pages(nearbypages)
        statement_pages = undoubled

        logger.info('returning statement_pages')
        return statement_pages


def select_correct_pages(pages_with_figure):
    """Selects pages from all pages with high numbers of key_figures found, on
    which statements probably are.
    """
    logger.info('selecting correct pages')
    pass

directory_in_str = '../all_reports'
directory = os.fsencode(directory_in_str)

data = {}

for file in os.listdir(directory):
    filename = os.fsdecode(file)
    if filename.endswith(".pdf"):
        pdfpath = "{}/{}".format(directory_in_str, filename)
        pdf = Pdf(pdfpath)
        textpath = pdf.create_textfile()
        print(textpath)

        termsfile = "termdictionary.json"
        language = "german"
        statement = Statement(textpath, termsfile, language)

        pages = statement.find_statement_pages()
        print(pages)
        data[filename] = pages

        today = date.today()
        today_string = today.strftime("%Y-%m-%d")
        name = "{}_statement_pages".format(today_string)


with open(name, "w") as jsonfile:
    json.dump(data, jsonfile)

        # filepath = '../report_samples/pdfminer_text/out2.txt'
# filepath = '../report_samples/Fuchs_GB_2018.txt'
