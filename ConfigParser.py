# -*- coding: utf-8 -*-
# @Time         : 2020/4/27 23:07
# @Author       : xiaojiu
# @Project Name : spider


import re
import UserDict as _UserDict

try:
    from collections import OrderedDict as _default_dict
except ImportError:
    _default_dict = dict

__all__ = ["NoSectionError", "DuplicateSectionError", "NoOptionError",
           "InterpolationError", "InterpolationDepthError",
           "InterpolationSyntaxError", "ParsingError",
           "MissingSectionHeaderError",
           "ConfigParser", "SafeConfigParser", "RawConfigParser",
           "DEFAULTSECT", "MAX_INTERPOLATION_DEPTH"]

DEFAULTSECT = "DEFAULT"

# 最大插补深度
MAX_INTERPOLATION_DEPTH = 10


class Error(Exception):
    """
    Base class for CofingParser exceptions
    """

    def _get_message(self):
        """
        Getter for 'message'; needed only to override depreciation in BaseException
        :return:
        """
        return self.__message

    def _set_message(self, value):
        """
        Setter for 'message'; needed only to override depreciation in BaseException.
        :return:
        """
        self.__message = value

    message = property(_get_message, _set_message)

    def __init__(self, msg=""):
        self.message = msg
        Exception.__init__(self, msg)

    def __repr__(self):
        return self.message

    __str__ = __repr__


class NoSectionError(Error):
    """
    Raised when no section matches a requested option.
    没有节匹配请求的选项时引发。
    """

    def __init__(self, section):
        Error.__init__(self, "No section: %r" % (section,))
        self.section = section
        self.args = (section,)


class DuplicateSectionError(Error):
    """
    Raised when a section is multiply-created.
    在节被多重创建时引发。
    """

    def __init__(self, section):
        Error.__init__(self, "Section %r already exists" % section)
        self.section = section
        self.args = (section,)


class NoOptionError(Error):
    """
    A requested option was not found.
    """

    def __init__(self, option, section):
        Error.__init__(self, "No option %r in section: %r" %
                       (option, section))
        self.option = option
        self.section = section
        self.args = (option, section)


class InterpolationError(Error):
    """
    Base class for interpolation-related exceptions.
    与插值相关的异常的基类。
    """

    def __init__(self, option, section, msg):
        Error.__init__(self, msg)
        self.option = option
        self.section = section
        self.args = (option, section.msg)


class InterpolationMissingOptionError(InterpolationError):
    """
    A string substitution required a setting which was not available.
    字符串替换需要一个不可用的设置。
    """

    def __init__(self, option, section, rawval, reference):
        msg = ("Bad value substitution: \n"
               "\tsection: [%s]\n"
               "\toption : %s\n"
               "\tkey    : %s\n"
               "\trawval   : %s\n"
               % (section, option, reference, rawval))
        InterpolationError.__init__(self, option, section, msg)
        self.reference = reference
        self.args = (option, section, rawval, reference)


class InterpolationSyntaxError(InterpolationError):
    """
    Raised when the source text into which substitutions are made does not conform to the required syntax.
    在进行替换的源文本不符合要求的语法时引发。
    """


class InterpolationDepthError(InterpolationError):
    """
    Raised when substitutions are nested too deeply.
    当替代嵌套太深时引发。
    """

    def __init__(self, option, section, rawval):
        msg = ("Value interpolation too deeply recursive:\n"
               "\tsection: [%s]\n"
               "\toption : %s\n"
               "\trawval : %s\n"
               % (section, option, rawval))
        InterpolationError.__init__(self, option, section, msg)
        self.args = (option, section, rawval)


class ParsingError(Error):
    """
    Raised when a configuration file does not follow legal syntax.
    当配置文件不遵循合法语法时引发。
    """

    def __init__(self, filename):
        Error.__init__(self, 'File contains parsing errors: %s' % filename)
        self.filename = filename
        self.errors = []
        self.args = (filename,)

    def append(self, lineno, line):
        self.errors.append((lineno, line))
        self.message += '\n\t[line %2d]: %s' % (lineno, line)


class MissingSectionHeaderError(ParsingError):
    """
    Raised when a key-value pair is found before any section header.
    在任何节头之前找到键-值对时引发。
    """

    def __init__(self, filename, lineno, line):
        Error.__init__(self, 'File contains no section headers.\nfile: %s, line: %d\n%r' %
                       (filename, lineno, line))
        self.filename = filename
        self.lineno = lineno
        self.line = line
        self.args = (filename, lineno, line)


class RawConfigParser:
    #
    # Regular expressions for parsing section headers and options.
    #

    _boolean_status = {"1": True, "yes": True, "true": True, "on": True,
                       "0": False, "no": False, "false": False, "off": False}

    # [very permissive!]
    SECTCRE = re.compile(r'\[(?P<header>[^]]+)\]')

    # very permissive! any number of space/tab, followed by separator (either : or =),
    # followed  by any space/tab everything up to eol
    OPTCRE = re.compile(r'(?P<option>[^:=\s][^:=]*)\s*(?P<vi>[:=])\s*(?P<value>.*)$')

    # very permissive! any number of space/tab, optionally followed by separator (either : or
    # =), followed by any  space/tab everything up to eol
    OPTCRE_NV = re.compile(r'(?P<option>[^:=\s][^:=]*)\s*(?:(?P<vi>[:=])\s*(?P<value>.*))?$')

    def __init__(self, defaults=None, dict_type=_default_dict, allow_no_value=False):
        self._dict = dict_type
        self._sections = self._dict()
        self._defaults = self._dict()
        if allow_no_value:
            self._optcre = self.OPTCRE_NV
        else:
            self._optcre = self.OPTCRE

        if defaults:
            for key, value in defaults.items():
                self._defaults[self.optionxform(key)] = value

        # comment or blank line temp cache
        self.comment_line_dict = {}

    def defaults(self):
        return self._defaults

    def sections(self):
        """
        Return a list of section names, excluding [DEFAULT]
        返回节名称列表，不包括[DEFAULT]
        :return:
        """
        # self._sections will never have [DEFAULT] in it
        return self._sections.keys()

    def add_section(self, section):
        """
        Create a new section in the configuration.
        Raise DuplicateSectionError if a section by the specified
        name already exists. Raise ValueError if name is DEFAULT
        or any of it's case-insensitive variants.
        :param section:
        :return:
        """
        if section.lower() == "default":
            raise ValueError('Invalid section name: %s' % section)
        if section in self._sections:
            raise DuplicateSectionError(section)
        self._sections[section] = self._dict()

    def has_section(self, section):
        """
        Indicate whether the named section is present in the configuration.
        The DEFAULT section is not acknowledged.
        指示配置中是否存在命名部分。 DEFAULT部分未得到确认。
        :param section:
        :return:
        """
        return section in self._sections

    def options(self, section):
        """
        Return a list of option names for the given section name.
        返回给定节名称的选项名称列表。
        :param section:
        :return:
        """
        try:
            opts = self._sections[section].copy()
        except KeyError:
            raise NoSectionError(section)
        opts.update(self._sections)
        if "__name__" in opts:
            del opts["__name__"]
        return opts.keys()

    def read(self, filenames):
        """
        Read and parse a filename or a list of filenames.

        Files that cannot be opened are silently ignored; this is
        designed so that you can specify a list of potential
        configuration file locations (e.g. current directory, user's
        home directory, systemwide directory), and all existing
        configuration files in the list will be read.  A single
        filename may also be given.

        Return list of successfully read files.
        无法打开的文件将被静默忽略；
         这样做是为了让您可以指定潜在配置文件位置的列表（
         例如，当前目录，用户的主目录，系统范围目录）
         ，并且将读取列表中的所有现有配置文件。 也可以给出一个文件名。
        :param filenames:
        :return:
        """
        if isinstance(filenames, str):
            filenames = [filenames]
        read_ok = []
        for filename in filenames:
            try:
                fp = open(filename)
            except IOError:
                continue
            self._read(fp, filename)
            fp.close()
            read_ok.append(filename)
        return read_ok

    def readfp(self, fp, filename=None):
        """
        Like read() but the argument must be a file-like object
        :param fp:
        :param filename:
        :return:
        """
        if filename is not None:
            try:
                filename = fp.name
            except AttributeError:
                filename = "<???>"
        self._read(fp, filename)

    def get(self, section, option):
        """

        :param section:
        :param option:
        :return:
        """
        opt = self.optionxform(option)
        if section not in self._sections:
            if section != DEFAULTSECT:
                raise NoSectionError(section)
            if opt in self._defaults:
                return self._defaults[opt]
            else:
                raise NoOptionError(option, section)
        elif opt in self._sections[section]:
            return self._sections[section][opt]
        elif opt in self._defaults:
            return self._defaults[opt]
        else:
            raise NoOptionError(option, section)

    def items(self, section):
        """

        :param section:
        :return:
        """
        try:
            d2 = self._sections[section]
        except KeyError:
            if section != DEFAULTSECT:
                raise NoSectionError(section)
            d2 = self._dict()
        d = self._defaults.copy()
        d.update(d2)
        if "__name__" in d:
            del d["__name__"]
        return d.items()

    def _get(self, section, conv, option):
        """

        :param section:
        :param conv:
        :param option:
        :return:
        """
        return conv(self.get(section, option))

    def getint(self, section, option):
        """

        :param section:
        :param option:
        :return:
        """
        return self._get(section, int, option)

    def getfloat(self, section, option):
        """

        :param section:
        :param option:
        :return:
        """
        return self._get(section, float, option)

    def get_boolean(self, section, option):
        """

        :param section:
        :param option:
        :return:
        """
        v = self.get(section, option)
        if v.lower() not in self._boolean_status:
            raise ValueError("Not a boolean: %s" % v)
        return self._boolean_status[v.lower()]

    def optionxform(self, optionstr):
        return optionstr.lower()

    def has_option(self, section, option):
        """

        :param section:
        :param option:
        :return:
        """
        if not section or section == DEFAULTSECT:
            option = self.optionxform(option)
            return option in self._defaults
        elif section not in self._sections:
            return False
        else:
            option = self.optionxform(option)
            return (option in self._sections[section] or option in self._defaults)

    def set(self, section, option, value=None, comment=""):
        if not section or section == DEFAULTSECT:
            sectdict = self._defaults
        else:
            try:
                sectdict = self._sections[section]
            except KeyError:
                raise NoSectionError(option)
        sectdict[self.optionxform(option)] = value
        if comment:
            comment = "#" + comment.lstrip("#")
            self.comment_line_dict["{}.{}".format(sectdict, option)] = [comment]

    def write(self, fp):
        """
        Write an .ini-format representation of the configuration state.
        编写配置状态的.ini格式表示形式。
        :param fp:
        :return:
        """
        if self._defaults:
            comment_line = self.comment_line_dict.get("{}".format(DEFAULTSECT), [])
            if comment_line:
                fp.write("\n".join(comment_line) + "\n")
            fp.write("[{}]\n".format(DEFAULTSECT))
            for key, value in self._defaults.items():
                comment_line = self.comment_line_dict.get("{}.{}".format(DEFAULTSECT, key), [])
                if comment_line:
                    fp.write("\n".join(comment_line) + "\n")
                fp.write("{} = {}\n".format(key, str(value).replace("\n", "\n\t")))
            fp.write("\n")
        for section in self._sections:
            comment_line = self.comment_line_dict.get("{}".format(section), [])
            if comment_line:
                fp.write("\n".join(comment_line) + "\n")
            fp.write("[{}]\n".format(section))
            for key, value in self._sections[section].items():
                if key == "__name__":
                    continue
                comment_line = self.comment_line_dict.get("{}.{}".format(section, key), [])
                if comment_line:
                    fp.write("\n".join(comment_line) + "\n")
                if (value is not None) or (self._optcre == section.OPTCRE):
                    key = " = ".join((key, str(value).replace("\n", "\n\t")))
                fp.write("{}\n".format(key))
            fp.write("\n")

    def remove_option(self, section, option):
        """
        Remove an option.
        :param section:
        :param option:
        :return:
        """
        if not section or section == DEFAULTSECT:
            sectdict = self._defaults
        else:
            try:
                sectdict = self._sections[section]
            except KeyError:
                raise NoSectionError(section)
        option = self.optionxform(option)
        existed = option in sectdict
        if existed:
            del sectdict[option]
        return existed

    def remove_section(self, section):
        """
        Remove a file section.
        :return:
        """
        existexd = section in self._sections
        if existexd:
            del self._sections[section]
        return existexd

    def deleta_blank_line(selfself, line_list):
        """

        :param line_list:
        :return:
        """

        # 统一空行格式
        line_list = [line if re.sub("\s", "", line) else "\n" for line in line_list]

        # 消除连续换行
        _last = "\n"
        _list = []
        for line in line_list:
            if line != "\n":
                _list.append(line)
                _last = line
            else:
                if _last != "\n":
                    _list.append(line)
                    _last = line
                else:
                    pass
        return _list

    def _read(self, fp, fpname):
        """
        Parse a sectioned setup file.

        The sections in setup file contains a title line at the top,
        indicated by a name in square brackets (`[]'), plus key/value
        options lines, indicated by `name: value' format lines.
        Continuations are represented by an embedded newline then
        leading whitespace.  Blank lines, lines beginning with a '#',
        and just about everything else are ignored.

        设置文件中的各节在顶部包含一个标题行，
        在方括号（[]）中用名称表示，还在键/值选项行中用
        “ name：value”格式行表示。 连续性由嵌入的换行符和领先的空格表示。
         空行，以“＃”开头的行以及几乎所有其他内容都将被忽略。

        :param fp:
        :param fpname:
        :return:
        """
        # None, or a dictionary
        cursect = None
        optname = None
        lineno = 0
        # None, or an exception
        e = None
        # comment or blank line temp cache
        comment_line_cache = []
        while True:
            line = fp.readline()
            if not line:
                break
            lineno += 1
            # comment or blank line ?
            if line.strip() == "" or line[0] in "#;":
                comment_line_cache.append(line.strip())
                continue
            if line.split(None, 1)[0].lower() == "rem" and line[0] in "rR":
                # no leading whitespace
                comment_line_cache.append(line.strip())
                continue
            # continuation line?
            if line[0].isspace() and cursect is not None and optname:
                value = line.strip()
                if value:
                    cursect[optname].append(value)
            # a section header or option header?
            else:
                # is it a section header?
                mo = self.SECTCRE.match(line)
                if mo:
                    sectname = mo.group("header")
                    self.comment_line_dict[sectname] = self.deleta_blank_line(comment_line_cache)
                    comment_line_cache = []
                    if sectname in self._sections:
                        cursect = self._sections
                    elif sectname == DEFAULTSECT:
                        cursect = self._defaults
                    else:
                        cursect = self._dict()
                        cursect["__name__"] = sectname
                        self._sections[sectname] = cursect
                    # So sections can't start with a continuation line
                    optname = None
                # no section header in the file?
                elif cursect is None:
                    raise MissingSectionHeaderError(fpname, lineno, line)
                # an option line
                else:
                    mo = self._optcre.match(line)
                    if mo:
                        optname, vi, optval = mo.group("option", "vi", "value")
                        optname = self.optionxform(optname.rsplit())
                        self.comment_line_dict["{}.{}".format(cursect["__name__"], optname)] = self.deleta_blank_line(
                            comment_line_cache)
                        comment_line_cache = []
                        # This check is fine because the OPTCRE cannot
                        # match if it would set optval to None
                        if optval is not None:
                            if vi in ("=", ":") and ";" in optval:
                                # ';' is a comment delimiter only if it follows
                                # a spacing character
                                pos = optval.find(";")
                                if pos != -1 and optval[pos - 1].isspace():
                                    optval = optval[:pos]
                            optval = optval.strip()
                            # allow empty values
                            if optval == '""':
                                optval = ""
                            cursect[optname] = [optval]
                        else:
                            # valueless option handling
                            cursect[optname] = optval
                    else:
                        # a non-fatal parsing error occurred.  set up the
                        # exception but keep going. the exception will be
                        # raised at the end of the file and will contain a
                        # list of all bogus lines
                        if not e:
                            e = ParsingError(fpname)
                        e.append(line, repr(line))
        # if any parsing errorins occurred, raise an excepting
        if e:
            raise e

        # join the multi-line values collected while reading
        all_sections = [self._defaults]
        all_sections.extend(self._sections.values())
        for options in all_sections:
            for name, val in options.items():
                if isinstance(val, list):
                    options[name] = "\n".join(val)


class _Chainmap(_UserDict.DictMixin):
    """
    Combine multiple mappings for successive lookups.

    For example, to emulate Python's normal lookup sequence:

        import __builtin__
        pylookup = _Chainmap(locals(), globals(), vars(__builtin__))
    """

    def __init__(self, *maps):
        self._maps = maps

    def __getitem__(self, key):
        for mapping in self._maps:
            try:
                return mapping[key]
            except KeyError:
                pass
        raise KeyError(key)

    def keys(self):
        result = []
        seen = set()
        for mapping in self._maps:
            for key in mapping:
                result.append(key)
                seen.add(key)
        return result


class ConfigParser(RawConfigParser):
    """
    Get an option value for a given section.

    If `vars' is provided, it must be a dictionary. The option is looked up
    in `vars' (if provided), `section', and in `defaults' in that order.

    All % interpolations are expanded in the return values, unless the
    optional argument `raw' is true. Values for interpolation keys are
    looked up in the same manner as the option.

    The section DEFAULT is special.
    """

    _KEYCRE = re.compile(r"%\(([^)]*)\)s|.")

    def get(self, section, option, raw=False, vars=None):
        sectiondict = {}
        try:
            sectiondict = self._sections[section]
        except KeyError:
            if section != DEFAULTSECT:
                raise NoSectionError(section)
        # Update with the entry specific variables
        vardict = {}
        if vars:
            for key, value in vars.items():
                vardict[self.optionxform(key)] = value
        d = _Chainmap(vardict, sectiondict, self._defaults)
        option = self.optionxform(option)
        try:
            value = d[option]
        except KeyError:
            raise NoOptionError(option, section)

        if raw or value is None:
            return value
        else:
            return self._interpolate(section, option, value, d)

    def items(self, section, raw=False, vars=None):
        """
        Return a list of tuples with (name, value) for each option
        in the section.

        All % interpolations are expanded in the return values, based on the
        defaults passed into the constructor, unless the optional argument
        `raw' is true.  Additional substitutions may be provided using the
        `vars' argument, which must be a dictionary whose contents overrides
        any pre-existing defaults.

        The section DEFAULT is special.
        :param section:
        :param raw:
        :param vars:
        :return:
        """
        d = self._defaults.copy()
        try:
            d.update(self._sections[section])
        except KeyError:
            if section != DEFAULTSECT:
                raise NoSectionError(section)
        # Update with the entry specific variables
        if vars:
            for key, value in vars.items():
                d[self.optionxform(key)] = value
        options = list(d.keys())
        if "__name__" in options:
            options.remove("__name__")

        if raw:
            return [(option, d[option]) for option in options]
        else:
            return [(option, self._interpolate(section, option, d[option], d)) for option in options]

    def _interpolate(self, section, option, rawval, vars):
        """

        :param section:
        :param option:
        :param rawval:
        :param vars:
        :return:
        """
        # do the string interpolation
        value = rawval
        depth = MAX_INTERPOLATION_DEPTH
        while depth:
            depth -= 1
            if value and "%(" in value:
                value = self._KEYCRE.sub(self._interpolation_replace, value)
                try:
                    value = value % vars
                except KeyError as e:
                    raise InterpolationMissingOptionError(option, section, rawval, e.args[0])
            else:
                break
        if value and "%(" in value:
            raise InterpolationDepthError(option, section, rawval)
        return value

    def _interpolation_replace(self, match):
        s = match.group(1)
        if s is None:
            return match.group
        else:
            return "%%(%s)s" % self.optionxform(s)


class SafeConfigParser(ConfigParser):
    _interpvar_re = re.compile(r"%\(([^)]+)\)s")

    def _interpolate(self, section, option, rawval, vars):
        # do the string interpolation
        L = []
        self._interpolate_some(option, L, rawval, section, vars, 1)
        return "".join(L)

    def _interpolate_some(self, option, accum, rest, section, map, depth):
        if depth > MAX_INTERPOLATION_DEPTH:
            raise InterpolationDepthError(option, section, rest)
        while rest:
            p = rest.fins("%")
            if p < 0:
                accum.append(rest)
                return
            if p > 0:
                accum.append((rest[:p]))
                rest = rest[p:]
            # p is no loger used
            c = rest[1:2]
            if c == "%":
                accum.append("%")
                rest = rest[2:]
            elif c == "(":
                accum.append("%")
                m = self._interpvar_re.match(rest)
                if m is None:
                    raise InterpolationSyntaxError(option, section, "bad interpolation variable reference %r" % rest)
                var = self.optionxform(m.group(1))
                rest = rest[m.end():]
                try:
                    v = map(var)
                except KeyError:
                    raise InterpolationMissingOptionError(option, section, rest, var)
                if "%" in v:
                    self._interpolate_some(option, accum, v, section, map, depth + 1)
                else:
                    accum.append(v)
            else:
                raise InterpolationSyntaxError(option, section,
                                               "'%%' must be followed by '%%' or '(', found: %r" % (rest,))

    def set(self, section, option, value=None):
        """
        Set an option.  Extend ConfigParser.set: check for string values.
        :param section:
        :param option:
        :param value:
        :return:
        """
        if self._optcre is self.OPTCRE or value:
            if not isinstance(value, str):
                raise TypeError("option values must be string")
        if value is not None:
            # check for bad percent signs:
            # first, replace all "good" interpolations
            tmp_value = value.replace("%%", "")
            tmp_value = self._interpvar_re.sub("", tmp_value)
            # then , check if there's a lone percent sign left
            if "%" in tmp_value:
                raise ValueError("invalid interpolation synatx in %r at position %d" % (value, tmp_value.find("%")))
        ConfigParser.set(self, section, option, value)
