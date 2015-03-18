# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# transformer.py
# Copyright (C) 2015 Fracpete (pythonwekawrapper at gmail dot com)


import os
import re
import javabridge
import math  # required for MathExpression
from weka.associations import Associator
import weka.core.serialization as serialization
import weka.filters as filters
import weka.flow.base as base
from weka.flow.base import InputConsumer, OutputProducer, Token
from weka.flow.container import ModelContainer
import weka.core.converters as converters
from weka.core.dataset import Instances
import weka.core.utils as utils
from weka.classifiers import Classifier, Evaluation, PredictionOutput
from weka.clusterers import Clusterer, ClusterEvaluation
from weka.core.classes import Random


class Transformer(InputConsumer, OutputProducer):
    """
    The ancestor for all sources.
    """

    def __init__(self, name=None, options=None):
        """
        Initializes the transformer.
        :param name: the name of the transformer
        :type name: str
        :param options: the dictionary with the options (str -> object).
        :type options: dict
        """
        super(InputConsumer, self).__init__(name=name, options=options)
        super(OutputProducer, self).__init__(name=name, options=options)

    def post_execute(self):
        """
        Gets executed after the actual execution.
        :return: None if successful, otherwise error message
        :rtype: str
        """
        result = super(Transformer, self).post_execute()
        if result is None:
            self._input = None
        return result


class PassThrough(Transformer):
    """
    Dummy actor that just passes through the data.
    """

    def __init__(self, name=None, options=None):
        """
        Initializes the transformer.
        :param name: the name of the transformer
        :type name: str
        :param options: the dictionary with the options (str -> object).
        :type options: dict
        """
        super(PassThrough, self).__init__(name=name, options=options)

    def description(self):
        """
        Returns a description of the actor.
        :return: the description
        :rtype: str
        """
        return "Dummy actor that just passes through the data."

    def do_execute(self):
        """
        The actual execution of the actor.
        :return: None if successful, otherwise error message
        :rtype: str
        """
        self._output.append(self.input)


class LoadDataset(Transformer):
    """
    Loads a dataset from a file.
    """

    def __init__(self, name=None, options=None):
        """
        Initializes the transformer.
        :param name: the name of the transformer
        :type name: str
        :param options: the dictionary with the options (str -> object).
        :type options: dict
        """
        super(LoadDataset, self).__init__(name=name, options=options)
        self._loader = None
        self._iterator = None

    def description(self):
        """
        Returns a description of the actor.
        :return: the description
        :rtype: str
        """
        return "Loads a dataset from a file. Either all at once or incrementally."

    @property
    def quickinfo(self):
        """
        Returns a short string describing some of the options of the actor.
        :return: the info, None if not available
        :rtype: str
        """
        return "incremental: " + str(self.options["incremental"]) \
               + ", custom: " + str(self.options["use_custom_loader"]) \
               + ", loader: " + base.to_commandline(self.options["custom_loader"])

    def fix_options(self, options):
        """
        Fixes the options, if necessary. I.e., it adds all required elements to the dictionary.
        :param options: the options to fix
        :type options: dict
        :return: the (potentially) fixed options
        :rtype: dict
        """
        opt = "incremental"
        if opt not in options:
            options[opt] = False
        if opt not in self.help:
            self.help[opt] = "Whether to load the dataset incrementally (bool)."

        opt = "use_custom_loader"
        if opt not in options:
            options[opt] = False
        if opt not in self.help:
            self.help[opt] = "Whether to use a custom loader."

        opt = "custom_loader"
        if opt not in options:
            options[opt] = converters.Loader(classname="weka.core.converters.ArffLoader")
        if opt not in self.help:
            self.help[opt] = "The custom loader to use (Loader)."

        return super(LoadDataset, self).fix_options(options)

    def to_options(self, k, v):
        """
        Hook method that allows conversion of individual options.
        :param k: the key of the option
        :type k: str
        :param v: the value
        :type v: object
        :return: the potentially processed value
        :rtype: object
        """
        if k == "custom_loader":
            return base.to_commandline(v)
        return super(LoadDataset, self).to_options(k, v)

    def from_options(self, k, v):
        """
        Hook method that allows converting values from the dictionary
        :param k: the key in the dictionary
        :type k: str
        :param v: the value
        :type v: object
        :return: the potentially parsed value
        :rtype: object
        """
        if k == "custom_loader":
            return utils.from_commandline(v, classname=utils.get_classname(converters.Loader()))
        return super(LoadDataset, self).from_options(k, v)

    def check_input(self, token):
        """
        Performs checks on the input token. Raises an exception if unsupported.
        :param token: the token to check
        :type token: Token
        """
        if token is None:
            raise Exception(self.full_name + ": No token provided!")
        if isinstance(token.payload, str):
            return
        raise Exception(self.full_name + ": Unhandled class: " + utils.get_classname(token.payload))

    def do_execute(self):
        """
        The actual execution of the actor.
        :return: None if successful, otherwise error message
        :rtype: str
        """
        fname = str(self.input.payload)
        if not os.path.exists(fname):
            return "File '" + fname + "' does not exist!"
        if not os.path.isfile(fname):
            return "Location '" + fname + "' is not a file!"
        if self.resolve_option("use_custom_loader"):
            self._loader = self.resolve_option("custom_loader")
        else:
            self._loader = converters.loader_for_file(fname)
        dataset = self._loader.load_file(fname, incremental=bool(self.resolve_option("incremental")))
        if not self.resolve_option("incremental"):
            self._output.append(Token(dataset))
        else:
            self._iterator = self._loader.__iter__()
        return None

    def has_output(self):
        """
        Checks whether any output tokens are present.
        :return: true if at least one output token present
        :rtype: bool
        """
        return super(LoadDataset, self).has_output() or (self._iterator is not None)

    def output(self):
        """
        Returns the next available output token.
        :return: the next token, None if none available
        :rtype: Token
        """
        if self._iterator is not None:
            try:
                inst = self._iterator.next()
                result = Token(inst)
            except Exception, e:
                self._iterator = None
                result = None
        else:
            result = super(LoadDataset, self).output()
        return result

    def stop_execution(self):
        """
        Triggers the stopping of the object.
        """
        super(LoadDataset, self).stop_execution()
        self._loader = None
        self._iterator = None

    def wrapup(self):
        """
        Finishes up after execution finishes, does not remove any graphical output.
        """
        self._loader = None
        self._iterator = None
        super(LoadDataset, self).wrapup()


class SetStorageValue(Transformer):
    """
    Store the payload of the current token in internal storage using the specified name.
    """

    def __init__(self, name=None, options=None):
        """
        Initializes the transformer.
        :param name: the name of the transformer
        :type name: str
        :param options: the dictionary with the options (str -> object).
        :type options: dict
        """
        super(SetStorageValue, self).__init__(name=name, options=options)

    def description(self):
        """
        Returns a description of the actor.
        :return: the description
        :rtype: str
        """
        return "Store the payload of the current token in internal storage using the specified name."

    @property
    def quickinfo(self):
        """
        Returns a short string describing some of the options of the actor.
        :return: the info, None if not available
        :rtype: str
        """
        return "name: " + str(self.options["storage_name"])

    def fix_options(self, options):
        """
        Fixes the options, if necessary. I.e., it adds all required elements to the dictionary.
        :param options: the options to fix
        :type options: dict
        :return: the (potentially) fixed options
        :rtype: dict
        """
        options = super(SetStorageValue, self).fix_options(options)

        opt = "storage_name"
        if opt not in options:
            options[opt] = "unknown"
        if opt not in self.help:
            self.help[opt] = "The storage value name for storing the payload under (string)."

        return options

    def do_execute(self):
        """
        The actual execution of the actor.
        :return: None if successful, otherwise error message
        :rtype: str
        """
        if self.storagehandler is None:
            return "No storage handler available!"
        self.storagehandler.storage[self.resolve_option("storage_name")] = self.input.payload
        self._output.append(self.input)
        return None


class DeleteStorageValue(Transformer):
    """
    Deletes the specified value from internal storage.
    """

    def __init__(self, name=None, options=None):
        """
        Initializes the transformer.
        :param name: the name of the transformer
        :type name: str
        :param options: the dictionary with the options (str -> object).
        :type options: dict
        """
        super(DeleteStorageValue, self).__init__(name=name, options=options)

    def description(self):
        """
        Returns a description of the actor.
        :return: the description
        :rtype: str
        """
        return "Deletes the specified value from internal storage."

    @property
    def quickinfo(self):
        """
        Returns a short string describing some of the options of the actor.
        :return: the info, None if not available
        :rtype: str
        """
        return "name: " + str(self.options["storage_name"])

    def fix_options(self, options):
        """
        Fixes the options, if necessary. I.e., it adds all required elements to the dictionary.
        :param options: the options to fix
        :type options: dict
        :return: the (potentially) fixed options
        :rtype: dict
        """
        options = super(DeleteStorageValue, self).fix_options(options)

        opt = "storage_name"
        if opt not in options:
            options[opt] = "unknown"
        if opt not in self.help:
            self.help[opt] = "The name of the storage value to delete (string)."

        return options

    def do_execute(self):
        """
        The actual execution of the actor.
        :return: None if successful, otherwise error message
        :rtype: str
        """
        if self.storagehandler is None:
            return "No storage handler available!"
        self.storagehandler.storage.pop(self.resolve_option("storage_name"), None)
        self._output.append(self.input)
        return None


class InitStorageValue(Transformer):
    """
    Initializes the storage value with the provided value (interpreted by 'eval' method).
    """

    def __init__(self, name=None, options=None):
        """
        Initializes the transformer.
        :param name: the name of the transformer
        :type name: str
        :param options: the dictionary with the options (str -> object).
        :type options: dict
        """
        super(InitStorageValue, self).__init__(name=name, options=options)

    def description(self):
        """
        Returns a description of the actor.
        :return: the description
        :rtype: str
        """
        return "Initializes the storage value with the provided value (interpreted by 'eval' method)."

    @property
    def quickinfo(self):
        """
        Returns a short string describing some of the options of the actor.
        :return: the info, None if not available
        :rtype: str
        """
        return "name: " + str(self.options["storage_name"]) + ", value: " + str(self.options["value"])

    def fix_options(self, options):
        """
        Fixes the options, if necessary. I.e., it adds all required elements to the dictionary.
        :param options: the options to fix
        :type options: dict
        :return: the (potentially) fixed options
        :rtype: dict
        """
        options = super(InitStorageValue, self).fix_options(options)

        opt = "storage_name"
        if opt not in options:
            options[opt] = "unknown"
        if opt not in self.help:
            self.help[opt] = "The name of the storage value to delete (string)."

        opt = "value"
        if opt not in options:
            options[opt] = "1"
        if opt not in self.help:
            self.help[opt] = "The initial value (string)."

        return options

    def do_execute(self):
        """
        The actual execution of the actor.
        :return: None if successful, otherwise error message
        :rtype: str
        """
        if self.storagehandler is None:
            return "No storage handler available!"
        self.storagehandler.storage[self.resolve_option("storage_name")] = eval(self.resolve_option("value"))
        self._output.append(self.input)
        return None


class UpdateStorageValue(Transformer):
    """
    Updates the specified storage value using the epxression interpreted by 'eval' method.
    The current value is available through the variable {X} in the expression.
    """

    def __init__(self, name=None, options=None):
        """
        Initializes the transformer.
        :param name: the name of the transformer
        :type name: str
        :param options: the dictionary with the options (str -> object).
        :type options: dict
        """
        super(UpdateStorageValue, self).__init__(name=name, options=options)

    def description(self):
        """
        Returns a description of the actor.
        :return: the description
        :rtype: str
        """
        return "Updates the specified storage value using the epxression interpreted by 'eval' method.\n"\
               "The current value is available through the variable {X} in the expression."

    @property
    def quickinfo(self):
        """
        Returns a short string describing some of the options of the actor.
        :return: the info, None if not available
        :rtype: str
        """
        return "name: " + str(self.options["storage_name"]) + ", expression: " + str(self.options["expression"])

    def fix_options(self, options):
        """
        Fixes the options, if necessary. I.e., it adds all required elements to the dictionary.
        :param options: the options to fix
        :type options: dict
        :return: the (potentially) fixed options
        :rtype: dict
        """
        options = super(UpdateStorageValue, self).fix_options(options)

        opt = "storage_name"
        if opt not in options:
            options[opt] = "unknown"
        if opt not in self.help:
            self.help[opt] = "The name of the storage value to delete (string)."

        opt = "expression"
        if opt not in options:
            options[opt] = "int({X} + 1)"
        if opt not in self.help:
            self.help[opt] = "The initial value (string)."

        return options

    def do_execute(self):
        """
        The actual execution of the actor.
        :return: None if successful, otherwise error message
        :rtype: str
        """
        if self.storagehandler is None:
            return "No storage handler available!"
        expr = str(self.resolve_option("expression")).replace(
            "{X}", str(self.storagehandler.storage[str(self.resolve_option("storage_name"))]))
        self.storagehandler.storage[self.resolve_option("storage_name")] = eval(expr)
        self._output.append(self.input)
        return None


class MathExpression(Transformer):
    """
    Calculates a mathematical expression. The placeholder {X} in the expression gets replaced by
    the value of the current token passing through. Uses the 'eval(str)' method for the calculation,
    therefore mathematical functions can be accessed using the 'math' library, e.g., '1 + math.sin({X})'.
    """

    def __init__(self, name=None, options=None):
        """
        Initializes the transformer.
        :param name: the name of the transformer
        :type name: str
        :param options: the dictionary with the options (str -> object).
        :type options: dict
        """
        super(MathExpression, self).__init__(name=name, options=options)

    def description(self):
        """
        Returns a description of the actor.
        :return: the description
        :rtype: str
        """
        return \
            "Calculates a mathematical expression. The placeholder {X} in the expression gets replaced by "\
            + "the value of the current token passing through. Uses the 'eval(str)' method for the calculation, "\
            + "therefore mathematical functions can be accessed using the 'math' library, e.g., '1 + math.sin({X})'."

    @property
    def quickinfo(self):
        """
        Returns a short string describing some of the options of the actor.
        :return: the info, None if not available
        :rtype: str
        """
        return "expression: " + str(self.options["expression"])

    def fix_options(self, options):
        """
        Fixes the options, if necessary. I.e., it adds all required elements to the dictionary.
        :param options: the options to fix
        :type options: dict
        :return: the (potentially) fixed options
        :rtype: dict
        """
        options = super(MathExpression, self).fix_options(options)

        opt = "expression"
        if opt not in options:
            options[opt] = "{X}"
        if opt not in self.help:
            self.help[opt] = "The mathematical expression to evaluate (string)."

        return options

    def do_execute(self):
        """
        The actual execution of the actor.
        :return: None if successful, otherwise error message
        :rtype: str
        """
        expr = str(self.resolve_option("expression"))
        expr = expr.replace("{X}", str(self.input.payload))
        self._output.append(Token(eval(expr)))
        return None


class ClassSelector(Transformer):
    """
    Sets/unsets the class index of a dataset.
    """

    def __init__(self, name=None, options=None):
        """
        Initializes the transformer.
        :param name: the name of the transformer
        :type name: str
        :param options: the dictionary with the options (str -> object).
        :type options: dict
        """
        super(ClassSelector, self).__init__(name=name, options=options)

    def description(self):
        """
        Returns a description of the actor.
        :return: the description
        :rtype: str
        """
        return "Sets/unsets the class index of a dataset."

    @property
    def quickinfo(self):
        """
        Returns a short string describing some of the options of the actor.
        :return: the info, None if not available
        :rtype: str
        """

        return "index: " + str(self.options["index"])

    def fix_options(self, options):
        """
        Fixes the options, if necessary. I.e., it adds all required elements to the dictionary.
        :param options: the options to fix
        :type options: dict
        :return: the (potentially) fixed options
        :rtype: dict
        """
        options = super(ClassSelector, self).fix_options(options)

        opt = "index"
        if opt not in options:
            options[opt] = "last"
        if opt not in self.help:
            self.help[opt] = "The class index (1-based number); 'first' and 'last' are accepted as well (string)."

        opt = "unset"
        if opt not in options:
            options[opt] = False
        if opt not in self.help:
            self.help[opt] = "Whether to unset the class index (bool)."

        return options

    def do_execute(self):
        """
        The actual execution of the actor.
        :return: None if successful, otherwise error message
        :rtype: str
        """
        data = self.input.payload
        index = str(self.resolve_option("index"))
        unset = bool(self.resolve_option("unset"))
        if unset:
            data.no_class()
        else:
            if index == "first":
                data.class_is_first()
            elif index == "last":
                data.class_is_last()
            else:
                data.class_index = int(index) - 1
        self._output.append(Token(data))
        return None


class Train(Transformer):
    """
    Trains the classifier/clusterer/associator on the incoming dataset and forwards a ModelContainer with the trained
    model and the dataset header.
    """

    def __init__(self, name=None, options=None):
        """
        Initializes the transformer.
        :param name: the name of the transformer
        :type name: str
        :param options: the dictionary with the options (str -> object).
        :type options: dict
        """
        super(Train, self).__init__(name=name, options=options)

    def description(self):
        """
        Returns a description of the actor.
        :return: the description
        :rtype: str
        """
        return \
            "Trains the classifier/clusterer/associator on the incoming dataset and forwards a ModelContainer with the trained " \
            + "model and the dataset header."

    @property
    def quickinfo(self):
        """
        Returns a short string describing some of the options of the actor.
        :return: the info, None if not available
        :rtype: str
        """
        return "setup: " + base.to_commandline(self.options["setup"])

    def fix_options(self, options):
        """
        Fixes the options, if necessary. I.e., it adds all required elements to the dictionary.
        :param options: the options to fix
        :type options: dict
        :return: the (potentially) fixed options
        :rtype: dict
        """
        options = super(Train, self).fix_options(options)

        opt = "setup"
        if opt not in options:
            options[opt] = Classifier(classname="weka.classifiers.rules.ZeroR")
        if opt not in self.help:
            self.help[opt] = "The classifier/clusterer/associator to train (Classifier/Clusterer/Associator)."

        return options

    def to_options(self, k, v):
        """
        Hook method that allows conversion of individual options.
        :param k: the key of the option
        :type k: str
        :param v: the value
        :type v: object
        :return: the potentially processed value
        :rtype: object
        """
        if k == "setup":
            return base.to_commandline(v)
        return super(Train, self).to_options(k, v)

    def from_options(self, k, v):
        """
        Hook method that allows converting values from the dictionary
        :param k: the key in the dictionary
        :type k: str
        :param v: the value
        :type v: object
        :return: the potentially parsed value
        :rtype: object
        """
        if k == "setup":
            try:
                return utils.from_commandline(v, classname=utils.get_classname(Classifier()))
            except Exception, e:
                try:
                    return utils.from_commandline(v, classname=utils.get_classname(Clusterer()))
                except Exception, e2:
                    return utils.from_commandline(v, classname=utils.get_classname(Associator()))
        return super(Train, self).from_options(k, v)

    def check_input(self, token):
        """
        Performs checks on the input token. Raises an exception if unsupported.
        :param token: the token to check
        :type token: Token
        """
        if isinstance(token.payload, Instances):
            return
        # if isinstance(token.payload, Instance):
        #     return
        raise Exception(self.full_name + ": Unhandled data type: " + str(token.payload.__class__.__name__))

    def do_execute(self):
        """
        The actual execution of the actor.
        :return: None if successful, otherwise error message
        :rtype: str
        """
        # TODO incremental classifiers/clusterers
        data = self.input.payload
        cls = self.resolve_option("setup")
        if isinstance(cls, Classifier):
            cls = Classifier.make_copy(cls)
            cls.build_classifier(data)
        elif isinstance(cls, Clusterer):
            cls = Clusterer.make_copy(cls)
            cls.build_clusterer(data)
        elif isinstance(cls, Associator):
            cls = Associator.make_copy(cls)
            cls.build_associations(data)
        else:
            return "Unhandled class: " + utils.get_classname(cls)
        cont = ModelContainer(model=cls, header=Instances.template_instances(data))
        self._output.append(Token(cont))
        return None


class Filter(Transformer):
    """
    Filters a dataset with the specified filter setup.
    Automatically resets the filter if the dataset differs.
    """

    def __init__(self, name=None, options=None):
        """
        Initializes the transformer.
        :param name: the name of the transformer
        :type name: str
        :param options: the dictionary with the options (str -> object).
        :type options: dict
        """
        super(Filter, self).__init__(name=name, options=options)
        self._filter = None
        self._header = None

    def description(self):
        """
        Returns a description of the actor.
        :return: the description
        :rtype: str
        """
        return "Filters a dataset with the specified filter setup.\n"\
               "Automatically resets the filter if the dataset differs."

    @property
    def quickinfo(self):
        """
        Returns a short string describing some of the options of the actor.
        :return: the info, None if not available
        :rtype: str
        """
        return "filter: " + base.to_commandline(self.options["filter"])

    def fix_options(self, options):
        """
        Fixes the options, if necessary. I.e., it adds all required elements to the dictionary.
        :param options: the options to fix
        :type options: dict
        :return: the (potentially) fixed options
        :rtype: dict
        """
        opt = "filter"
        if opt not in options:
            options[opt] = filters.Filter(classname="weka.filters.AllFilter")
        if opt not in self.help:
            self.help[opt] = "The filter to apply to the dataset (Filter)."

        return super(Filter, self).fix_options(options)

    def to_options(self, k, v):
        """
        Hook method that allows conversion of individual options.
        :param k: the key of the option
        :type k: str
        :param v: the value
        :type v: object
        :return: the potentially processed value
        :rtype: object
        """
        if k == "filter":
            return base.to_commandline(v)
        return super(Filter, self).to_options(k, v)

    def from_options(self, k, v):
        """
        Hook method that allows converting values from the dictionary
        :param k: the key in the dictionary
        :type k: str
        :param v: the value
        :type v: object
        :return: the potentially parsed value
        :rtype: object
        """
        if k == "filter":
            return utils.from_commandline(v, classname=utils.to_commandline(filters.Filter()))
        return super(Filter, self).from_options(k, v)

    def check_input(self, token):
        """
        Performs checks on the input token. Raises an exception if unsupported.
        :param token: the token to check
        :type token: Token
        """
        if token is None:
            raise Exception(self.full_name + ": No token provided!")
        if isinstance(token.payload, Instances):
            return
        raise Exception(self.full_name + ": Unhandled class: " + utils.get_classname(token.payload))

    def do_execute(self):
        """
        The actual execution of the actor.
        :return: None if successful, otherwise error message
        :rtype: str
        """
        # TODO: incremental filtering
        data = self.input.payload
        if (self._filter is None) or self._header.equal_headers(data) is not None:
            self._header = Instances.template_instances(data)
            self._filter = filters.Filter.make_copy(self.resolve_option("filter"))
            self._filter.inputformat(data)
        filtered = self._filter.filter(data)
        self._output.append(Token(filtered))
        return None


class DeleteFile(Transformer):
    """
    Deletes the incoming files that match the regular expression.
    """

    def __init__(self, name=None, options=None):
        """
        Initializes the transformer.
        :param name: the name of the transformer
        :type name: str
        :param options: the dictionary with the options (str -> object).
        :type options: dict
        """
        super(DeleteFile, self).__init__(name=name, options=options)

    def description(self):
        """
        Returns a description of the actor.
        :return: the description
        :rtype: str
        """
        return "Deletes the incoming files that match the regular expression."

    @property
    def quickinfo(self):
        """
        Returns a short string describing some of the options of the actor.
        :return: the info, None if not available
        :rtype: str
        """
        return "regexp: " + str(self.options["regexp"])

    def fix_options(self, options):
        """
        Fixes the options, if necessary. I.e., it adds all required elements to the dictionary.
        :param options: the options to fix
        :type options: dict
        :return: the (potentially) fixed options
        :rtype: dict
        """
        options = super(DeleteFile, self).fix_options(options)

        opt = "regexp"
        if opt not in options:
            options[opt] = ".*"
        if opt not in self.help:
            self.help[opt] = "The regular expression that the files must match (string)."

        return options

    def do_execute(self):
        """
        The actual execution of the actor.
        :return: None if successful, otherwise error message
        :rtype: str
        """
        fname = str(self.input.payload)
        spattern = str(self.resolve_option("regexp"))
        pattern = None
        if (spattern is not None) and (spattern != ".*"):
            pattern = re.compile(spattern)
        if (pattern is None) or (pattern.match(fname)):
            os.remove(fname)
        self._output.append(self.input)
        return None


class CrossValidate(Transformer):
    """
    Cross-validates the classifier/clusterer on the incoming dataset. In case of a classifier, the Evaluation object
    is forwarded. For clusterers the loglikelihood.
    """

    def __init__(self, name=None, options=None):
        """
        Initializes the transformer.
        :param name: the name of the transformer
        :type name: str
        :param options: the dictionary with the options (str -> object).
        :type options: dict
        """
        super(CrossValidate, self).__init__(name=name, options=options)

    def description(self):
        """
        Returns a description of the actor.
        :return: the description
        :rtype: str
        """
        return "Cross-validates the classifier/clusterer on the incoming dataset. In case of a classifier, the "\
               "Evaluation object is forwarded. For clusterers the loglikelihood."

    @property
    def quickinfo(self):
        """
        Returns a short string describing some of the options of the actor.
        :return: the info, None if not available
        :rtype: str
        """
        return "setup: " + base.to_commandline(self.options["setup"]) + ", folds: " + str(self.options["folds"])

    def fix_options(self, options):
        """
        Fixes the options, if necessary. I.e., it adds all required elements to the dictionary.
        :param options: the options to fix
        :type options: dict
        :return: the (potentially) fixed options
        :rtype: dict
        """
        options = super(CrossValidate, self).fix_options(options)

        opt = "setup"
        if opt not in options:
            options[opt] = Classifier(classname="weka.classifiers.rules.ZeroR")
        if opt not in self.help:
            self.help[opt] = "The classifier/clusterer to train (Classifier/Clusterer)."

        opt = "folds"
        if opt not in options:
            options[opt] = 10
        if opt not in self.help:
            self.help[opt] = "The number of folds for CV (int)."

        opt = "seed"
        if opt not in options:
            options[opt] = 1
        if opt not in self.help:
            self.help[opt] = "The seed value for randomizing the data (int)."

        opt = "discard_predictions"
        if opt not in options:
            options[opt] = False
        if opt not in self.help:
            self.help[opt] = "Discard classifier predictions to save memory (bool)."

        opt = "output"
        if opt not in options:
            options[opt] = None
        if opt not in self.help:
            self.help[opt] = "For capturing the classifier's prediction output (PredictionOutput)."

        return options

    def to_options(self, k, v):
        """
        Hook method that allows conversion of individual options.
        :param k: the key of the option
        :type k: str
        :param v: the value
        :type v: object
        :return: the potentially processed value
        :rtype: object
        """
        if k == "setup":
            return base.to_commandline(v)
        if k == "output":
            return base.to_commandline(v)
        return super(CrossValidate, self).to_options(k, v)

    def from_options(self, k, v):
        """
        Hook method that allows converting values from the dictionary
        :param k: the key in the dictionary
        :type k: str
        :param v: the value
        :type v: object
        :return: the potentially parsed value
        :rtype: object
        """
        if k == "setup":
            try:
                return utils.from_commandline(v, classname=utils.get_classname(Classifier()))
            except Exception, e:
                return utils.from_commandline(v, classname=utils.get_classname(Clusterer()))
        if k == "output":
            return utils.from_commandline(v, classname=utils.get_classname(PredictionOutput()))
        return super(CrossValidate, self).from_options(k, v)

    def do_execute(self):
        """
        The actual execution of the actor.
        :return: None if successful, otherwise error message
        :rtype: str
        """
        data = self.input.payload
        cls = self.resolve_option("setup")
        if isinstance(cls, Classifier):
            cls = Classifier.make_copy(cls)
            evl = Evaluation(data)
            evl.discard_predictions = bool(self.resolve_option("discard_predictions"))
            evl.crossvalidate_model(
                cls,
                data,
                int(self.resolve_option("folds")),
                Random(int(self.resolve_option("seed"))),
                self.resolve_option("output"))
            self._output.append(Token(evl))
        elif isinstance(cls, Clusterer):
            cls = Clusterer.make_copy(cls)
            evl = ClusterEvaluation()
            llh = evl.crossvalidate_model(
                cls,
                data,
                int(self.resolve_option("folds")),
                Random(int(self.resolve_option("seed"))))
            self._output.append(Token(llh))
        else:
            return "Unhandled class: " + utils.get_classname(cls)
        return None


class EvaluationSummary(Transformer):
    """
    Generates a summary string from an Evaluation object.
    """

    def __init__(self, name=None, options=None):
        """
        Initializes the transformer.
        :param name: the name of the transformer
        :type name: str
        :param options: the dictionary with the options (str -> object).
        :type options: dict
        """
        super(EvaluationSummary, self).__init__(name=name, options=options)

    def description(self):
        """
        Returns a description of the actor.
        :return: the description
        :rtype: str
        """
        return "Generates a summary string from an Evaluation object."

    @property
    def quickinfo(self):
        """
        Returns a short string describing some of the options of the actor.
        :return: the info, None if not available
        :rtype: str
        """
        return "title: " + str(self.options["title"]) \
               + ", complexity: " + str(self.options["complexity"]) \
               + ", matrix: " + str(self.options["matrix"])

    def fix_options(self, options):
        """
        Fixes the options, if necessary. I.e., it adds all required elements to the dictionary.
        :param options: the options to fix
        :type options: dict
        :return: the (potentially) fixed options
        :rtype: dict
        """
        options = super(EvaluationSummary, self).fix_options(options)

        opt = "title"
        if opt not in options:
            options[opt] = None
        if opt not in self.help:
            self.help[opt] = "The title for the output (string)."

        opt = "complexity"
        if opt not in options:
            options[opt] = False
        if opt not in self.help:
            self.help[opt] = "Whether to output complexity information (bool)."

        opt = "matrix"
        if opt not in options:
            options[opt] = False
        if opt not in self.help:
            self.help[opt] = "Whether to output the confusion matrix (bool)."

        return options

    def do_execute(self):
        """
        The actual execution of the actor.
        :return: None if successful, otherwise error message
        :rtype: str
        """
        evl = self.input.payload
        summary = evl.summary(title=self.resolve_option("title"), complexity=bool(self.resolve_option("complexity")))
        if bool(self.resolve_option("matrix")):
            summary += "\n" + evl.matrix(title=self.resolve_option("title"))
        self._output.append(Token(summary))
        return None


class ModelReader(Transformer):
    """
    Reads the serialized model (Classifier/Clusterer) from disk and forwards a ModelContainer.
    """

    def __init__(self, name=None, options=None):
        """
        Initializes the transformer.
        :param name: the name of the transformer
        :type name: str
        :param options: the dictionary with the options (str -> object).
        :type options: dict
        """
        super(ModelReader, self).__init__(name=name, options=options)

    def description(self):
        """
        Returns a description of the actor.
        :return: the description
        :rtype: str
        """
        return "Reads the serialized model from disk and forwards a ModelContainer."

    def do_execute(self):
        """
        The actual execution of the actor.
        :return: None if successful, otherwise error message
        :rtype: str
        """
        fname = self.input.payload
        data = serialization.read_all(fname)
        if len(data) == 1:
            if javabridge.is_instance_of(data[0], "weka/classifiers/Classifier"):
                cont = ModelContainer(model=Classifier(jobject=data[0]))
            elif javabridge.is_instance_of(data[0], "weka/clusterers/Clusterer"):
                cont = ModelContainer(model=Clusterer(jobject=data[0]))
            else:
                return "Unhandled class: " + utils.get_classname(data[0])
        elif len(data) == 2:
            if javabridge.is_instance_of(data[0], "weka/classifiers/Classifier"):
                cont = ModelContainer(model=Classifier(jobject=data[0]), header=Instances(data[1]))
            elif javabridge.is_instance_of(data[0], "weka/clusterers/Clusterer"):
                cont = ModelContainer(model=Clusterer(jobject=data[0]), header=Instances(data[1]))
            else:
                return "Unhandled class: " + utils.get_classname(data[0])
        else:
            return "Expected 1 or 2 objects, but got " + str(len(data)) + " instead reading: " + fname
        self._output.append(Token(cont))
        return None
