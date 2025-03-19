#!/usr/bin/env python
# coding: utf-8

import os
import yaml

class PapersToPubList:
    def __init__(self, paper_yaml, publications_md):
        """
        # Read paper yaml file and convert it into a publication markdown file.

        Expects to get paths to paper_yaml and publications_md as arguments.

        Will create publications_md if it does not exist.

        Can get absolute paths or paths relative to the current working directory.

        # Expected YAML format for papers file is as follows.

        papers:
          - title:
            authors:
            journal:
            year:
            link:
            figure:
            caption:

          - title:
            authors:
            journal:
            year:
            link:
            figure:
            caption:

          [...]
        """

        try:
            assert(os.path.isfile(paper_yaml)), f"Error: must specify valid file path to paper yaml file."
            self.path_paper = paper_yaml
            self.path_publist = publications_md
        except AssertionError as msg:
            print(msg)
            raise

        self.do_task()


    def do_task(self):
        papers = None

        with open(self.path_paper) as paper_yaml:
            papers = yaml.safe_load(paper_yaml)

        with open(self.path_publist, "w") as pubfile:
            # define helper lambda wl to Write a Line
            wl = lambda s="": pubfile.write(f"{s}\n")
            wl(r"```yaml")
            wl(r"title: Publications")
            wl(r"number_headings: True")
            wl(r"```")
            wl()
            wl(r"As my publication record illustrates, I research best by collaborating with other scientists.")
            wl()
            wl(r"# Publication Listings")
            wl()
            wl(r"- [Publications (PDF)](research/willcox_publications.pdf)")
            wl(r"- [Google Scholar Page](https://scholar.google.com/citations?hl=en&user=5Ns_t38AAAAJ)")
            wl(r"- [Publications on NASA ADS](https://ui.adsabs.harvard.edu/search/fq=%7B!type%3Daqp%20v%3D%24fq_database%7D&fq_database=(database%3Aastronomy%20OR%20database%3Aphysics)&p_=0&q=author%3A%22willcox%2C%20d.%20e.%22%20year%3A2016-&sort=date%20desc%2C%20bibcode%20desc)")
            wl(r"- [Preprints on the arXiv](https://arxiv.org/search/astro-ph?searchtype=author&query=Willcox,+D+E)")
            wl()
            wl(r"---")
            wl()
            for paper in papers["papers"]:
                title = paper["title"]
                figure = paper["figure"]
                caption = paper["caption"]
                authors = paper["authors"]
                year = paper["year"]
                journal = paper["journal"]
                link = paper["link"]

                wl(f"# {title}")
                wl()
                wl(r"```yaml")
                wl(r"class: Figure")
                wl(f"source: \"{figure}\"")
                wl(f"caption: \"{caption}\"")
                wl(r"```")
                wl()
                wl(f"- {authors}")
                wl(f"- {year}, {journal}")
                wl(f"- [{link}]({link})")
                wl()
            wl(r"---")
