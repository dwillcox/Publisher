#!/usr/bin/env python
# coding: utf-8

"""
The Publisher code is a collection of Python classes to make
publishing markdown content easy using a combination of
GitHub-Flavored Markdown and YAML-defined objects.

Currently it supports a webpage output, but it would be "easy" to
generate LaTeX documents, Beamer slides, etc.

D. Willcox
"""

import inspect
import copy
import os
import re
import glob
import yaml
import json
import markdown
from jinja2 import Environment, FileSystemLoader, Template, DebugUndefined


# Define some generic data container classes

# A Dataset is a combination of list and dictionary data.
#
# Dataset metadata may be stored in the dictionary,
# while dataset entries are storied in the list, etc.
#
# An entry may be an Entry object or a complex data structure.
class Dataset:
    def __init__(self, *args, **kwargs):
        self.m_list = list(copy.deepcopy(args))
        self.m_dict = dict(copy.deepcopy(kwargs))

    def __iter__(self):
        return iter(self.m_list)

    def archive_entry(self, entry):
        self.m_list.append(copy.deepcopy(entry))

    def archive_attribute(self, key, value):
        self.m_dict[key] = copy.deepcopy(value)

    def unpack_and_archive(self, other):
        # unpack the attributes from other into this dataset
        self.m_dict = {**self.m_dict, **other.attributes()}

        # unpack the entries from other into this dataset
        for e in other.entries():
            self.archive_entry(e)

    def get(self, idx):
        try:
            if isinstance(idx, int):
                return self.m_list[idx]
            elif isinstance(idx, str):
                return self.m_dict[idx]
            assert(False), f"Error: index must be either int or str type."
        except AssertionError as msg:
            print(msg)
            raise

    def entries(self):
        return self.m_list

    def attributes(self):
        return self.m_dict

    def has_entries(self):
        return len(self.m_list) > 0

    def has_attributes(self):
        return len(self.m_dict.keys()) > 0

    def has_content(self):
        return self.has_entries() or self.has_attributes()

    def render_dict(self, **kwargs):
        # This is a recursive function
        #
        # Recurse through the entries in order, returning
        # dictionaries of {"context": [container type name, e.g. ParallelSet or SerialSet],
        #                  "class": [self type name],
        #                  "attributes": [dictionary of self.attributes()],
        #                  "entries": list of entries}
        data = {}
        data["context"] = kwargs["context"]
        data["class"] = type(self).__name__
        data["attributes"] = self.m_dict
        data["entries"] = [entry.render_dict(**{**kwargs, **{"context": type(self).__name__}}) for entry in self.entries()]
        return data

# A ParallelSet is typically a time-parallel set of entries.
#
# They are meant to be evaluated in parallel.
class ParallelSet(Dataset):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# A SerialSet is typically a time-ordered set of entries.
#
# They are meant to be evaluated in serial.
#
# This could be a set of datasets, or it could be a set of content objects.
#
# If it is the latter case, then it is helpful to think of the SerialSet as an Entry.
#
# The Entry is title + related content.
#
# An Entry could be untitled plain text.
#
# An Entry could be a heading plus plain text.
#
# An Entry could be a heading with text and one or more figures.
#
# Whatever the case, these are meant to focus on one precise topic.
#
# A Scene may need only one Entry, or it may require multiple entries
# to communicate an idea relating multiple precise topics.
class SerialSet(Dataset):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


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
                    self.relpath = os.path.relpath(path, start=self.cwd)
                else:
                    self.relpath = os.path.relpath(path, start=self.cwd)
                    self.abspath = os.path.join(self.cwd, self.relpath)

                # raise an error if this location does not specify a file
                assert(os.path.isfile(self.abspath)), f"Error: no file found at path {path}"
            except AssertionError as msg:
                print(msg)
                raise

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
            raise

        # create a Location object and return it
        return Location(abspath)


class Yaml(Dataset):
    def __init__(self, *args, **kwargs):
        """
        This class contains YAML-formatted data.

        Supports either list or dictionary data.
        """
        super().__init__(*args, **kwargs)

    def render_dict(self, **kwargs):
        # This is a recursive function
        #
        # Recurse through the entries in order, returning
        # dictionaries of {"context": [container type name, e.g. ParallelSet or SerialSet],
        #                  "class": [self type name],
        #                  "attributes": [dictionary of self.attributes()],
        #                  "entries": list of entries}
        data = {}
        data["context"] = kwargs["context"]
        data["class"] = type(self).__name__
        data["attributes"] = self.m_dict
        data["attributes"].pop("location", None) # we do not need to output the Yaml location object
        data["entries"] = [e for e in self.entries()]
        return data


class Text:
    def __init__(self, content_string, location=Location()):
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
            raise

        try:
            assert isinstance(location, Location), f"Error: {location} is not of expected type: Location"
            self.location = location
        except AssertionError as msg:
            print(msg)
            raise

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

    def render_dict(self, target=None, **kwargs):
        """
        Returns a dictionary containing all Text content.

        If target is "html" then run any HTML preprocessing
        needed for this content first.

        This is useful for rendering using Jinja2.
        """

        data = {}
        data["context"] = kwargs["context"]
        data["class"] = type(self).__name__
        data["attributes"] = {"content": ""}
        data["entries"] = []

        try:
            if (not target) or (target == "markdown"):
                data["attributes"]["content"] = self.raw_string
            elif target == "html":
                data["attributes"]["content"] = self.as_html()
            else:
                assert(not target), f"Error: unrecognized target {target}"
        except AssertionError as msg:
            print(msg)
            raise

        return data


class Figure:
    def __init__(self, source="", title="", caption="", location=Location()):
        """
        This class contains a YAML-defined figure.

        Requires:
        - content_string: a single string containing the YAML-formatted definition for a figure.
        - location: the Location object storing this figure's YAML specification
        """
        try:
            assert isinstance(source, str), f"Error: Figure source {source} is not of expected type: str"
            assert source != "", f"Error: Figure requires a source path to an image file but got: {source}"
            self.source = source

            assert isinstance(title, str), f"Error: Figure title {title} is not of expected type: str"
            self.title = title

            assert isinstance(caption, str), f"Error: Figure caption {caption} is not of expected type: str"
            self.caption = caption

            assert isinstance(location, Location), f"Error: Figure declaration location {location} is not of expected type: Location"
            self.location = location
        except AssertionError as msg:
            print(msg)
            raise

        # locate relative and absolute paths to source image
        self.locate_source()

    def locate_source(self):
        """
        Returns the YAML specification where the figure image path
        relative to the figure specification file is replaced
        by its path relative to the current directory.
        """
        source_location = self.location.locate_relpath(self.source)
        self.relpath = source_location.relpath
        self.abspath = source_location.abspath

    def render_dict(self, **kwargs):
        """
        Returns a dictionary containing all Figure content.

        This is useful for rendering using Jinja2.
        """

        data = {}
        data["context"] = kwargs["context"]
        data["class"] = type(self).__name__
        data["attributes"] = {"source": self.source,
                              "relpath": self.relpath,
                              "abspath": self.abspath,
                              "title": self.title,
                              "caption": self.caption}
        data["entries"] = []

        return data


# This is a factory class for constructing
# content objects from YAML-formatted specifications.
class ContentFactory:
    def __init__(self, *args):
        # Interpret positional argument list as the
        # list of classes we can construct
        self.classes = args

        # Check that all content classes can be constructed
        for i, cls in enumerate(self.classes):
            try:
                assert(inspect.isclass(cls)), f"Error: received invalid class for positional argument with index {i}"
            except AssertionError as msg:
                print(msg)
                raise

    ## Define a helper function to get the list of
    ## keyword arguments supported by a class
    def get_supported_keywords(self, a_class):
        supported_keywords = []
        supported_arguments = inspect.signature(a_class.__init__).parameters.values()
        for a_arg in supported_arguments:
            if a_arg.kind == a_arg.POSITIONAL_OR_KEYWORD or a_arg.kind == a_arg.KEYWORD_ONLY:
                supported_keywords.append(a_arg.name)
        return supported_keywords

    def construct(self, cls, *args, **kwargs):
        # Check if the requested class is permitted for this factory
        try:
            assert(cls in self.classes), f"Error: cannot construct a class for which this factory was not configured. Factory supports these classes: {c.__name__ for c in self.classes}"
        except AssertionError as msg:
            print(msg)
            raise

        # Classes do not expect their classname in the keyword list.
        #
        # We just need it to pick which class to construct.
        kwargs.pop("class", None)

        # Construct class with the given arguments
        xobj = cls(*args, **kwargs)

        ## Return the newly-constructed object to the caller
        return xobj


# Define classes for reading and storing the content associated with a single Scene
#
# We have to be a little fancy because the text content combines traditional
# GitHub-flavored Markdown with YAML-specified content classes to denote figures, etc.

# Current state of the content reader
class ReaderState:
    def __init__(self):
        # state variables
        #
        # m_reading_yaml: True if we are "reading YAML"
        #                 False otherwise
        #
        # m_content: A single string storing reader content.
        #
        # m_class_label: The label for the class of our content.
        #
        # m_class_map: The mappings between each class label and the Class.
        #
        # m_class_factory: The ContentFactory we use to construct objects.
        self.m_declaration = None
        self.m_content = None
        self.m_class_label = None
        self.m_class_map = None
        self.m_class_factory = None

        # initialize state
        self.reset()

    def reset(self):
        # Re-initialize the class
        self.set_not_declaration()
        self.clear_content()
        self.define_classes()

    def set_not_declaration(self):
        # set the "reading a declaration" state to False
        self.m_declaration = False

    def set_declaration(self):
        # set the "reading a declaration" state to True
        self.m_declaration = True

    def is_declaration(self):
        # return True if we are "reading a declaration",
        # otherwise return False.
        return self.m_declaration

    def set_class_label(self, class_label="__auto__"):
        # if auto, then try to figure out the label ourselves
        if class_label=="__auto__":
            try:
                assert(self.has_content()), f"Error: cannot auto-identify a class label without content."
                data = yaml.safe_load(self.m_content)
                if isinstance(data, dict):
                    if "class" in data.keys():
                        self.m_class_label = self.m_class_map[data["class"]].__name__
                    else:
                        self.m_class_label = Yaml.__name__
                elif isinstance(data, list):
                    self.m_class_label = Yaml.__name__
                else:
                    self.m_class_label = Text.__name__
            except AssertionError as msg:
                print(msg)
                raise
        else:
            # else, raise an error if we do not recognize the label
            # otherwise, set the class label for our reader content
            try:
                assert(class_label in self.m_class_map.keys()), f"Error: cannot identify unknown content class: {class_label}"
                self.m_class_label = class_label
            except AssertionError as msg:
                print(msg)
                raise

    def clear_content(self):
        # clears stored content
        self.m_content = ""
        self.m_class_label = None

    def define_classes(self):
        # Types of content blocks we recognize
        # and their mappings to class constructors
        self.m_class_map = {Text.__name__: Text,
                            Yaml.__name__: Yaml,
                            Figure.__name__: Figure}

        self.m_class_factory = ContentFactory(*[cls for _,cls in self.m_class_map.items()])

    def store_content(self, new_content):
        # stores new content
        self.m_content += new_content

    def content(self):
        # returns reader content
        return self.m_content

    def is_empty(self):
        # check if content is null,
        # i.e. equivalent to the empty string or None
        empty_string = ""
        none_type = None

        null_similarity = lambda a,b: (a is b) or (bool(a) is bool(b)) or (a==b)

        if null_similarity(self.m_content, none_type):
            return True
        else:
            return null_similarity(self.m_content.strip(), empty_string)

    def has_content(self):
        # return True if we have content, False otherwise
        return not self.is_empty()

    def content_to_dict(self):
        # interprets the content as YAML and return a dictionary of the results
        content_dict = yaml.safe_load(self.m_content)
        return content_dict

    def construct_content_object(self, **kwargs):
        # call the class constructor for our reader content and
        # return the resulting object while
        # passing through any keyword arguments that
        # the constructor needs
        try:
            assert(self.m_class_label in self.m_class_map.keys()), f"Error: cannot construct unknown content class: {self.m_class_label}"

            # make a data structure for the positional and keyword
            # arguments our class requires
            cls_args = {"args": [], "kwargs": {}}

            if self.m_class_label == Text.__name__:
                # form the arguments expected by the Text.__init__ constructor
                cls_args["args"] = [self.m_content]
                cls_args["kwargs"] = kwargs
            else:
                # convert yaml-specified arguments into positional and
                # keyword arguments for class construction
                yaml_args = self.content_to_dict()

                # allow user to specify an args list explicitly
                if "args" in yaml_args.keys():
                    cls_args["args"] = yaml_args["args"][:]

                # allow user to specify a kwargs dict explicitly
                if "kwargs" in yaml_args.keys():
                    for k,v in yaml_args["kwargs"].items():
                        cls_args["kwargs"][k] = v

                # allow user to specify keywords (k) and values (v) as "k: v" entries
                for k,v in yaml_args.items():
                    # we've already accounted for explicit args and kwargs entries
                    # so we interpret all other entries as "key: value" keyword arguments
                    if k != "args" and k != "kwargs":
                        cls_args["kwargs"][k] = v

                # finally, add the kwargs from this function caller
                cls_args["kwargs"] = {**cls_args["kwargs"], **kwargs}

            content_object = self.m_class_factory.construct(self.m_class_map[self.m_class_label], *cls_args["args"], **cls_args["kwargs"])
        except AssertionError as msg:
            print(msg)
            raise
        return content_object


# A class for reading Markdown files containing YAML-specified content classes
class MarkDownFile:
    def __init__(self, filename):
        """
        Initialize class data from filename.

        Filename is an absolute path.

        Each Markdown file contains GitHub-flavored markdown text interspersed with YAML-defined figures.

        The Markdown file represents the content for a single Scene as a set of one or more Datasets.

        Each Dataset stores one or more Datasets, each containing a set of Entries.

        Each Entry is itself a set of Content Objects

        This hierarchy enables Scenes to have sections with subsections.

        Further subdivision is not very useful because a Scene usually represents two-dimensional visual data
        laid out vertically first, with each entry along a column possibly
        extending horizontally in a row of Entries.

        This class thus transforms a file into a hierarchy of Entries, each a list of Content Objects.
        """
        self.content = SerialSet()

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
            raise

        # Store the filename (no extension) as the top level dataset name
        self.content.archive_attribute("name", self.name)

        # read the markdown file contents
        self.read()

    def get_content(self):
        """
        Returns the dataset of entries in the file
        """
        return self.content

    def read(self):
        """
        Open the file and read GitHub-Flavored Markdown,
        allowing for YAML-formatted Python object declarations.

        Declare Python objects by decorating a code block:

        ```yaml
        class: [Class Name]
        args:
          - arg1
          - arg2
          [...]
        kwargs:
          kw1: kw_value_1
          kw2: kw_value_2
          [...]
        ```

        Alternately, you can use only keyword arguments like so:

        ```yaml
        class: [Class Name]
        kw1: kw_value_1
        kw2: kw_value_2
        [...]
        ```

        Note this is distinct from a code block we consider
        simply part of the GitHub Markdown specification like so:

        ```
        [Class Name](*args, **kwargs)
        ```

        In the second case, because we do not find both a "yaml" decoration
        and a class keyword entry, we do not map the yaml block to a class.

        We simply interpret the code block as part of its surrounding markdown.

        If the "class" keyword is omitted but the code block is decorated
        with a yaml declaration, then the code block contents are interpreted
        as yaml-formatted data and added to the global file metadata.

        For example, this could be the top of the file:

        ```yaml
        title: Scene Title
        subtitle: Scene Subtitle
        ```

        And we will read the YAML data into the Scene global Dataset attributes.

        Here is the algorithm for creating a content hierarchy that
        supports one level of markdown headings denoted by "#" as well
        as YAML sequences specifying global attributes or content objects.

        We want to fill the global SerialSet.

        We start out reading content objects into a temporary SerialSet.

        def helper(finish_serial=False):
            store the current reader state in the temporary SerialSet

            if finish_serial:
                if a temporary ParallelSet does not exist:
                    save the temporary SerialSet, if it is not empty, into the global SerialSet
                else:
                    save the temporary SerialSet, it if is not empty, into the ParallelSet

                create a new temporary SerialSet

        if we find a YAML sequence:
            read the YAML sequence into a content raw string

            convert it to a dict through the YAML interpreter

            if that dict has no class key:
                store the dict's (key,value) map in the global SerialSet attributes.
            else:
                convert the dict to a content object
                append it to the temporary SerialSet list by calling helper(finish_serial=False)

        if we are reading a text sequence:
            if we encounter a heading marker "#" or a line consisting of at least 3 dashes "---":
                helper(finish_serial=True)

                if heading:
                    name the new temporary SerialSet using the heading name
                    create a new temporary ParallelSet if it does not exist

                elif dashes:
                    save the ParallelSet, if it is not empty, as a new entry into the global SerialSet
                    set the ParallelSet to None

            else:
                use the temporary SerialSet to resume reading content objects

        when we encounter end-of-file:
            helper(finish_serial=True)

            if a temporary ParallelSet exists:
                save the ParallelSet, if it is not empty, as a new entry into the global SerialSet
        """

        # Keep track of the current reader state
        state = ReaderState()

        # Temporary variables for building the content hierarchy
        tmp_serial_set = SerialSet()
        tmp_parallel_set = None

        # Helper function to construct content as we
        # encounter individual content blocks in the file.
        def construct_content_and_reset(_serial_set, _parallel_set, _state, finish_serial=False):
            # store content only if we have read any content
            if _state.has_content():
                # automatically figure out the content class
                _state.set_class_label()

                # create content object from reader state
                xobj = _state.construct_content_object(location=self.location)

                if type(xobj).__name__ == Yaml.__name__:
                    # If xobj stores raw yaml, store that in the temp serial set attributes
                    #
                    # NOTE: if xobj is raw yaml, it is meaningless for it to have an unlabeled list
                    #       so any such data will be discarded.
                    for k,v in xobj.attributes().items():
                        # omit archiving the location, we already have this information elsewhere
                        if k != "location":
                            _serial_set.archive_attribute(k,v)
                else:
                    # otherwise store xobj content in the temp serial set entries
                    _serial_set.archive_entry(xobj)

            # if we need to finish serial content accumulation, then
            # check if ParallelSet exists and store temporary SerialSet
            if finish_serial:
                if _serial_set.has_content():
                    if _parallel_set is None:
                        self.content.unpack_and_archive(_serial_set)
                    else:
                        _parallel_set.archive_entry(_serial_set)

                # create a new temporary SerialSet
                _serial_set = SerialSet()

            # in any case, reset the reader state
            _state.reset()

            # return tuple of positional args
            return (_serial_set, _parallel_set, _state)

        # Read content from our file
        with open(self.location.relpath, "r") as file:
            # Loop through the lines in the file, reading content
            for linenumber, line in enumerate(file, start=1):
                # To make this easy, let's move to lowercase and eliminate all whitespace
                lowercase_nospaces = re.sub(r"\s", r"", line.lower())

                if not state.is_declaration() and lowercase_nospaces.startswith(r"```"):
                    # If we are not reading a YAML declaration,
                    # check if we are entering a YAML declaration.
                    #
                    # Distinguish a YAML-formatted object declaration
                    # from a ```-delimited code block
                    if lowercase_nospaces == r"```yaml":
                        tmp_serial_set, tmp_parallel_set, state = construct_content_and_reset(tmp_serial_set,
                                                                                              tmp_parallel_set,
                                                                                              state,
                                                                                              finish_serial=False)
                        state.set_declaration()
                    elif lowercase_nospaces != r"```":
                        try:
                            assert(False), f"Error: read unknown content declaration {lowercase_nospaces} on line {linenumber} of file {self.location.abspath}"
                        except AssertionError as msg:
                            print(msg)
                            raise
                elif lowercase_nospaces == r"```":
                    # If we are reading a YAML declaration,
                    # check if we are exiting the YAML declaration.
                    tmp_serial_set, tmp_parallel_set, state = construct_content_and_reset(tmp_serial_set,
                                                                                          tmp_parallel_set,
                                                                                          state,
                                                                                          finish_serial=False)
                    state.set_not_declaration()
                else:
                    # We are neither entering nor exiting a YAML block.
                    if state.is_declaration():
                        # If we are currently reading a YAML block,
                        # store the current line in the reader state.
                        state.store_content(line)
                    else:
                        # Otherwise we are currently reading Markup text.

                        # Check if we encountered a heading marker: "#"
                        at_heading = lowercase_nospaces.startswith(r"#")

                        # Check if we encountered a line with nothing but 1 or more dashes: "-" (possibly repeated)
                        at_dashes = lowercase_nospaces != "" and re.sub(r"-", r"", lowercase_nospaces) == ""

                        if at_heading or at_dashes:
                            # if we are at a heading or at dashes, then
                            # organize our content into serial or parallel sets
                            tmp_serial_set, tmp_parallel_set, state = construct_content_and_reset(tmp_serial_set,
                                                                                                  tmp_parallel_set,
                                                                                                  state,
                                                                                                  finish_serial=True)

                            if at_heading:
                                if tmp_parallel_set is None:
                                    tmp_parallel_set = ParallelSet()
                                heading_text = line.strip().lstrip(r"#")
                                tmp_serial_set.archive_attribute("name", heading_text)
                            elif at_dashes:
                                if tmp_parallel_set.has_content():
                                    self.content.archive_entry(tmp_parallel_set)
                                tmp_parallel_set = None
                        else:
                            # we are neither at a heading nor at dashes so
                            # we must be at ordinary markup text and we can
                            # store the current line into the reader state
                            state.store_content(line)

            # After looping through the file,
            # construct any remaining content in our reader state.
            #
            # Also store our serial or parallel sets into the global dataset.
            tmp_serial_set, tmp_parallel_set, state = construct_content_and_reset(tmp_serial_set,
                                                                                  tmp_parallel_set,
                                                                                  state,
                                                                                  finish_serial=True)
            #
            if tmp_parallel_set is not None:
                if tmp_parallel_set.has_content():
                    self.content.archive_entry(tmp_parallel_set)
                tmp_parallel_set = None


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

    def render_dict(self, **kwargs):
        """
        Returns a dictionary containing all Scene content.

        This is useful for rendering using Jinja2.
        """

        dictout = {"glance": self.glance, "source": self.source}

        # add any attributes from our content dictionary
        try:
            for k,v in self.content.attributes().items():
                assert k not in dictout.keys(), f"Error: content attribute {k} shadows dictionary keys!"
                dictout[k] = v
        except AssertionError as msg:
            print(msg)
            raise

        # transform content entries into the dictionary key "content"
        try:
            assert "content" not in dictout.keys(), f"Error: attribute 'content' shadows reserved key!"
        except AssertionError as msg:
            print(msg)
            raise

        dictout["content"] = self.content.render_dict(**{**kwargs, **{"context": type(self.content).__name__}})

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
        reader = ReaderYAML()
        sequence_spec_loc = Location(path)
        sequence_spec = reader.read(sequence_spec_loc.relpath)

        return cls.from_dict(sequence_spec, pointer=sequence_spec_loc)

    def render_dict(self, **kwargs):
        """
        Returns a dictionary containing all Sequence content.

        This is useful for rendering using Jinja2.
        """

        dictout = {"author": self.author, "title": self.title}
        dictout["sequence"] = [s.render_dict(**kwargs) for s in self.sequence]

        with open("render_sequence.json", "w") as file:
            for idx, scene in enumerate(dictout["sequence"]):
                file.write(f"// Writing Scene {idx}:\n\n")
                file.write(json.dumps(scene, indent=4))
                file.write(f"\n\n\n")

        return dictout


# The Webpage is a single HTML page we wish to render from a Sequence
#
class Webpage:
    def __init__(self, sequence):
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

        content_data = self.sequence.render_dict(target="html")

        # First, let's sanity-check that the content contains no conflicting
        # dictionary keys with the configuration and assert an error otherwise
        try:
            common_keys = set(config_data.keys()) & set(content_data.keys())
            assert len(common_keys) == 0, f"Error: content YAML shadows one or more configuration settings!\nCheck common keys: {common_keys}"
        except AssertionError as msg:
            print(msg)
            raise

        # Form the data to feed into the template rendering
        render_data = {**config_data, **content_data}

        # Load template file specified
        j2env = Environment(loader=FileSystemLoader(os.path.dirname(html_template)), undefined=DebugUndefined)
        j2tmp = j2env.get_template(os.path.basename(html_template))

        # Use Jinja2 to render the template and create output HTML data
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
            data = {**data, **yaml.safe_load(file)}
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
            data = {**data, **self.read(f)}

        # Return Dictionary of YAML Data
        return data

