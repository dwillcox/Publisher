#!/usr/bin/env python
# coding: utf-8

"""
The Publisher code is a collection of Python classes to make
publishing markdown content easy using YAML-defined structure.

Currently it supports a webpage output, but it would be easy to
generate LaTeX documents, Beamer slides, etc.

D. Willcox
"""

import os
import glob
import yaml
import markdown
from jinja2 import Environment, FileSystemLoader, Template, DebugUndefined


# Define content classes for each type
class Location:
    def __init__(self, path=os.getcwd()):
        """
        Stores location as both relative and absolute paths to content.

        By convention in Publisher content, content locations
        are always relative to their containing data structures.

        But this is not the same as relative to the current
        working directory where the Publisher code is invoked.

        For example, the location of a Sequence is the relative
        path between the current working directory where Publisher
        is invoked and the Sequence specification file.

        The location of a Scene within the Sequence is the relative
        path between the Sequence location and the source file
        specifying the Scene.

        The location of a Text or Figure element is the same as the 
        location of the source file where the text or figure
        specification appears.

        Note that the Figure specification contains a path attribute
        which should be a relative path to the image file from
        the file containing the Figure specification.

        I think it is clearest to keep related content together,
        so when I use Publisher, I will always keep Scene specification
        files in the same directory as image files they reference.

        In practice, these could be symbolic links, however.

        In any case, when preprocessing the Figure class,
        we will need to change the path attribute so that it
        is relative to the location of the current working directory.

        The final rendering step does usually require some way
        to compute the absolute path, hence the Location class.
        """

        # store the current working directory
        self.cwd = os.getcwd()

        if path == self.cwd:
            self.relpath = None
            self.abspath = None
            self.directory = self.cwd
        else:
            try:
                # compute the absolute and relative paths to the file
                if os.path.isabs(path):
                    self.abspath = path
                    self.relpath = os.path.relpath(path, start=cwd)
                else:
                    self.relpath = os.path.relpath(path, start=cwd)
                    self.abspath = os.path.join(cwd, self.relpath)

                # raise an error if this location does not specify a file
                assert(os.path.isfile(self.abspath)), f"Error: no file found at path {path}"
            except AssertionError as msg:
                print(msg)

            # save the (absolute) directory path containing this location
            self.directory = os.path.dirname(self.abspath)

    def locate_relpath(self, path):
        """
        Given a path to a file, return its Location object.

        Requires the path specified to an actual file
        relative to the directory containing this location.
        """

        # compute the absolute path to the file
        abspath = os.path.join(self.directory, path)

        # check the path is valid
        try:
            assert(os.path.isfile(abspath)), f"Error: no file found at path {abspath} from relative path {path}."
        except AssertionError as msg:
            print(msg)

        # create a Location object and return it
        return Location(abspath)


class Text:
    def __init__(self, content_string, location):
        """
        This class contains a block of plain text.

        Requires:
        - content_string: a single string containing text content.
        - location: the Location object storing this figure's YAML specification
        """
        try:
            assert isinstance(content_string, str), f"Error: {content_string} is not of expected type: str"
            self.raw_string = content_string
        except AssertionError as msg:
            print(msg)

        try:
            assert isinstance(location, Location), f"Error: {location} is not of expected type: Location"
            self.location = location
        except AssertionError as msg:
            print(msg)

    def as_html(self):
        # Preprocess Markdown before converting to HTML
        #
        # - Convert every newline character into a HTML line break.
        #
        #   This marks every blank-line separated text block as its own paragraph,
        #   while consecutive lines are part of the same paragraph.
        mdpp = "\n<br/>\n".join(self.raw_string.split("\n"))

        # Convert Markdown to HTML
        html = markdown.markdown(mdpp)

        return html

    def render_dict(self, target=None):
        """
        Returns a dictionary containing all Text content.

        If target is "html" then run any HTML preprocessing
        needed for this content first.

        This is useful for rendering using Jinja2.
        """

        dictout = {"type": "text"}

        try:
            if (not target) or (target == "markdown"):
                dictout["content"] = self.raw_string
            elif target == "html":
                dictout["content"] = self.as_html()
            else:
                assert(not target), f"Error: unrecognized target {target}"
        except AssertionError as msg:
            print(msg)

        return dictout


class Figure:
    def __init__(self, content_string, location):
        """
        This class contains a YAML-defined figure.

        Requires:
        - content_string: a single string containing the YAML-formatted definition for a figure.
        - location: the Location object storing this figure's YAML specification
        """
        try:
            assert isinstance(content_string, str), f"Error: {content_string} is not of expected type: str"
            self.raw_string = content_string
        except AssertionError as msg:
            print(msg)

        try:
            assert isinstance(location, Location), f"Error: {location} is not of expected type: Location"
            self.location = location
        except AssertionError as msg:
            print(msg)
        
        # convert figure specification to YAML-structured dictionary
        self.yaml = yaml.safe_load(self.raw_string)
        
        # locate relative and absolute paths to source image
        self.locate_source()

    def locate_source(self):
        """
        Returns the YAML specification where the figure image path
        relative to the figure specification file is replaced
        by its path relative to the current directory.
        """
        source_location = self.location.locate_relpath(self.yaml["source"])
        self.yaml["source_relpath"] = source_location.relpath
        self.yaml["source_abspath"] = source_location.abspath

    def render_dict(self, target=None):
        """
        Returns a dictionary containing all Figure content.

        This is useful for rendering using Jinja2.
        """

        dictout = {"type": "figure",
                   "content": self.yaml}

        return dictout


# Define a class for storing the content associated with a single Scene
class MarkDownFile:
    def __init__(self, filename):
        """
        Initialize class data from filename.

        Filename is an absolute path.
        
        Each Markdown file contains GitHub-flavored markdown text interspersed with YAML-defined figures.

        This class transforms such a file into a list of dictionaries.

        Each dictionary represents either text or figure content.
        """
        self.content = []
        
        # get the file's basename (no directories)
        self.basename = os.path.basename(filename)
        # store the file's location
        self.location = Location(filename)

        # strip the .md extension
        self.name, extension = os.path.splitext(self.basename)
        try:
            assert extension == ".md", f"Error: file {filename} lacks a .md extension!"
        except AssertionError as msg:
            print(msg)
        
        # read the markdown file contents
        self.read()

    def get_content(self):
        """
        Returns the list of content objects in the file
        """
        return self.content

    def read(self):
        """
        open the filename specified and read data
        allowing for YAML definitions delimited by a
        #yaml pragma in a code block like so:
        
        ```#yaml
        [yaml definitions here]
        ```
        
        Note this is distinct from a code block we consider
        simply part of the markdown like so:
        
        ```yaml
        [example yaml syntax here]
        ```
        
        In the second case, because we do not find the pragma,
        we do not interpret the code block to contain
        YAML definitions for the preprocessor.
        """

        reading_yaml = False

        # Types of content blocks we read: "text", "figure"
        tmp_read_type = "text"
        tmp_string = ""

        def store_tmp_block():
            if tmp_read_type == "text":
                self.content.append(Text(tmp_string, self.location))
            elif tmp_read_type == "figure":
                self.content.append(Figure(tmp_string, self.location))
        
        file = open(self.location.relpath, "r")
        for line in file:
            if not reading_yaml and line.strip() == "```#yamlFigure":
                reading_yaml = True
                store_tmp_block()
            elif reading_yaml and line.strip() == "```":
                reading_yaml = False
                store_tmp_block()
            else:
                tmp_string += line
        file.close()


# Define a Scene, the smallest complete composition frame.
#
# - For fiction writing, this is a literal scene.
# - For nonfiction, this is a section or possibly subsection.
# - For presentations, this is a slide.
# - For websites, this is a page.
#
# Whatever the target, a Scene cannot be further subdivided
#     without breaking the content flow.
class Scene:
    def __init__(self, scene_dict, pointer=Location()):
        """
        Initialize Scene from a Python dictionary.

        Requires:
        - scene_dict: Python dictionary storing the following keys:
                      ("glance", "source")
        """
        self.glance = scene_dict["glance"]
        self.source = scene_dict["source"]
        self.pointer = pointer

        # Read the content from the source Markdown file
        source_loc = self.pointer.locate_relpath(self.source)
        self.content = MarkDownFile(source_loc.relpath).get_content()

    def render_dict(self, target=None):
        """
        Returns a dictionary containing all Scene content.

        This is useful for rendering using Jinja2.
        """

        dictout = {"glance": self.glance, "source": self.source}
        dictout["content"] = [c.render_dict(target) for c in self.content]

        return dictout


# Define a Sequence containing an ordered set of Scenes.
#
# I imagine a Sequence as a complete work.
#
# However, it could be a chapter or a single website page.
#
# That is more consistent with the way the code is currently written
# and strikes me as more easily extensible.
#
class Sequence:
    def __init__(self):
        return

    @classmethod
    def from_dict(cls, sequence_dict, pointer=Location()):
        """
        Initialize Sequence of Scene objects from a Python dictionary.

        Requires:
        - sequence_dict: Python dictionary storing the following keys:
                         ("author", "title", "sequence")
                         author: string
                         title: string
                         sequence: list of dicts, each to be a Scene
        """
        sequence = cls()

        sequence.author = sequence_dict["author"]
        sequence.title = sequence_dict["title"]
        sequence.pointer = pointer 
        sequence.sequence = [Scene(s, pointer) for s in sequence_dict["sequence"]]

        return sequence

    @classmethod
    def from_path(cls, path):
        """
        Construct and return a Sequence from a YAML specification in
        the given path.
        """
        sequence_spec_loc = Location(path)
        sequence_spec = reader.read(sequence_spec_loc.relpath)

        return cls.from_dict(sequence_spec, pointer=sequence_spec_loc)

    def render_dict(self, target=None):
        """
        Returns a dictionary containing all Sequence content.

        This is useful for rendering using Jinja2.
        """

        dictout = {"author": self.author, "title": self.title}
        dictout["sequence"] = [s.render_dict(target) for s in self.sequence]
        
        return dictout


# The Webpage is a single HTML page we wish to render from a Sequence
#
class Webpage:
    def __init__(self):
        """
        The Webpage is a class that transforms a Sequence into an HTML page.
        """
        self.template = None
        self.sequence = None
        self.config = {}
        self.sequence = sequence

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        return

    def using_sequence(self, sequence):
        """
        Specify the Sequence the webpage will read from.
        """
        self.sequence = sequence

        # Returns self so we can use it in a Python "with" statement.
        return self

    def using_template(self, html_template):
        """
        Specify the HTML template the webpage will render.
        """
        self.template = html_template

        # Returns self so we can use it in a Python "with" statement.
        return self

    def using_config(self, config):
        """
        Specify the dictionary of configuration settings for rendering.
        """
        self.config = config

        # Returns self so we can use it in a Python "with" statement.
        return self

    def render_html(self):
        """
        Uses Jinja2 to render HTML using our template and content.

        Relies on inputs:
        - html_template: path to a Jinja2-templated HTML file
                        (will replace .j2 extension with .html)
        - config_data: Python dictionary storing configuration settings 
        - content_data: Python dictionary storing YAML-formatted content files
        """

        html_template = self.template

        if len(self.config.keys()) == 0:
            print("Warning: rendering a website without configuration may leave some template settings unmatched.")
        config_data = self.config

        content_data = self.sequence.render_dict()

        # First, let's sanity-check that the content contains no conflicting
        # dictionary keys with the configuration and assert an error otherwise
        try:
            common_keys = set(config_data.keys()) & set(content_data.keys())
            assert len(common_keys) == 0, f"Error: content YAML shadows one or more configuration settings!\nCheck common keys: {common_keys}"
        except AssertionError as msg:
            print(msg)

        # Form the data to feed into the template rendering
        render_data = config_data | content_data

        # Load template file specified
        j2env = Environment(loader=FileSystemLoader(os.path.dirname(html_template)), undefined=DebugUndefined)
        j2tmp = j2env.get_template(os.path.basename(html_template))

        # Use Jinja2 to render the template and create output HTML data
        render_data = config_data | content_data
        html_out = j2tmp.render(render_data)

        # Write output HTML data to an HTML file
        filename, extension = os.path.splitext(os.path.basename(html_template))
        output_file = f"{filename}.html"
        with open(output_file, "w") as file:
            file.write(html_out)


# We will need a helper class to safely read one or more YAML files.
#
class ReaderYAML:
    def __init__(self):
        """
        Helper functions for reading YAML files.
        """

    def read(self, yaml_abs_path):
        """
        Get a specific file referenced with an absolute path to a .yaml file.
        """
        data = {}
        with open(yaml_abs_path, "r") as file:
            data = data | yaml.safe_load(file)
        return data


    def glob(self, yaml_abs_path):
        """
        Loops through all *.yaml files in the absolute path
        provided as an argument. Returns the database of YAML
        entries as a single Python dictionary.
        """
        data = {}

        # Glob the YAML files in the specified directory
        data_files = glob.glob(os.path.join(yaml_abs_path, "*.yaml"))


        # Loop through Configuration files and Read YAML
        for f in data_files:
            data = data | self.read(f)

        # Return Dictionary of YAML Data
        return data


if __name__ == "__main__":
    # About directories, this is intended to be executed from the root
    # website directory where the Makefile lives.
    #
    # The directory where the Makefile lives is the current working directory.
    #
    # Get current working directory
    cwd = os.getcwd()

    # Make a YAML Reader to help us read website source files.
    reader = ReaderYAML()

    # Get Webpage configuration data from all YAML files in source directory
    config = reader.glob(os.path.join(cwd, "source"))

    # Read Webpage Sequence specification from YAML file in content directory
    sequence_path = os.path.join(cwd, "content", "webpage.yaml")

    # Construct Sequence
    sequence = Sequence.from_path(sequence_path)

    # Identify HTML template(s) for the website
    templates = glob.glob(os.path.join(cwd, "source", "*.j2"))

    # Render Webpages from Sequence
    with Webpage() as webpage:
        with webpage.using_sequence(sequence) as webpage:
            with webpage.using_config(config) as webpage:
                for template in templates:
                    with webpage.using_template(template) as webpage:
                        webpage.render_html()

