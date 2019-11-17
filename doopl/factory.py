# --------------------------------------------------------------------------
# Source file provided under Apache License, Version 2.0, January 2004,
# http://www.apache.org/licenses/
# (c) Copyright IBM Corp. 2018
# --------------------------------------------------------------------------

from doopl.opl import *
import pandas as pd
from six import iteritems
from collections import OrderedDict

from contextlib import contextmanager
import sys

OPL_INTEGER = 1
OPL_FLOAT = 2
OPL_STRING = 3




@contextmanager
def create_opl_model(model, data=None):
    """
    Use this method to create an OplModel from a .mod file.
    This OplModel can be linked to 0 to n .dat files.
    Use the OplModel methods to set inputs via list of tuples, or pandas dataframes.
    Use the OplModel to generate and solve the problem, get the solution...
    :param mode: .mod file to read. Can be a file path or an IO object with a read method
    :param data: can be nothing, or the name of a .dat file or a list of .dat files
    :return: an OplModel instance
    """
    _env = IloEnv()

    _modelSource = None
    _filename = None
    if isinstance(model, str):
        _modelSource = IloOplModelSource(_env, model)
        _filename = model
    else:
        _modelSource = IloOplModel__makeModelSourceFromString(_env, model.read())

    opl = _env._createOplModel(_modelSource)

    ret = OplModel(_env, opl, _filename)
    if data is not None:
        if isinstance(data, str):
            ret.set_input(data)
        elif isinstance(data, list):
            for t in data:
                ret.set_input(t)
        else:
            raise ValueError("bad data argument for create_opl_model")
    try:
        yield ret
    finally:
        # Code to release resource, e.g.:
        ret.end()


class MyDataSource(IloOplDataSourceWrapper):
    def __init__(self, opl, inputs):
        """ Internal undocumented class"""
        IloOplDataSourceWrapper.__init__(self, opl.getEnv())
        self._opl = opl
        self._inputs = inputs

    def read(self):
        dh = self.getDataHandler()
        env = self._opl.getEnv()
        getFields = self._opl._getFields

        for (name, value) in iteritems(self._inputs):
            set = dh._prepareSet(name)
            schema = set.getSchema()

            fields, fieldsSize = getFields(schema)

            def addCell(cells, index, f, v):
                if f == OPL_STRING:
                    if isinstance(v, str):
                        cells.setStringValue(index, v)
                    elif type(v) in {int, float}:
                        cells.setStringValue(index, str(v))
                    elif sys.version_info[0] == 2 and isinstance(v, unicode):
                        cells.setStringValue(index, str(v).encode("utf-8"))
                    else:
                        cells.setStringValue(index, str(v))
                else:
                    cells.setNumValue(index, float(v))

            def fillTupleSet(set, values):
                size = len(bycolumn[0])
                for i, type in enumerate(fields):
                    col = bycolumn[i]
                    if type == OPL_INTEGER:
                        set.setIntColumnValues(i, col, size)
                    elif type == OPL_FLOAT:
                        set.setNumColumnValues(i, col, size)
                    else:
                        values = []
                        for v in bycolumn[i]:
                            if isinstance(v, str):
                                values.append(v)
                            elif type(v) in {int, float}:
                                values.append(str(v))
                            elif sys.version_info[0] == 2 and isinstance(v, unicode):
                                values.append(str(v).encode("utf-8"))
                            else:
                                values.append(str(v))
                        set.setStringColumnValues(i, values, size)
                        values = None
                set.fillTupleHash()

            if isinstance(value, list):
                bycolumn = [list(i) for i in zip(*(col for col in value))]
                fillTupleSet(set, bycolumn)
                bycolumn = None
            else:
                if isinstance(value, pd.DataFrame):
                    bycolumn = [value[n].tolist() for n in value.columns]
                    if schema.getSize() != len(bycolumn):
                        tuple_names = [schema.getColumnName(i) for i in range(0, schema.getSize())]
                        message = 'Column mistmatch, input name=%s, expected = %s, data = %s' % (name, tuple_names, [n for n in value.columns])
                        raise OplRuntimeException(message)
                    fillTupleSet(set, bycolumn)
                    bycolumn = None
                else:
                    hasKey = schema.hasKey()
                    commitMethod = set.commit if hasKey is True else set.commit2HashTable
                    cells = IloTupleCellArray(env, fieldsSize)
                    for v in value:
                        for (i, t) in enumerate(v):
                            addCell(cells, i, fields[i], t)
                        commitMethod(cells, False)

                    if hasKey is False:
                        set.fillColumns()
                    cells.end()

class OplModel(object):
    """
    This class represents an OPL Model, that is a .mod file which is linked to .dat files, python tuple lists or python dataframes.
    """
    def __init__(self, env, opl, filename = None):
        self._env = env
        self._opl = opl
        self._inputs = OrderedDict()
        self._datfiles = []
        self._cplex_quality = None
        self._cplex_stats = None
        self._filename = filename
        self._fieldDict = {}

    def getEnv(self):
        return self._env

    def _getFields(self, schema):
        f = self._fieldDict.get(schema, None)
        if f is None:
            f = schema._getColumnTypes()
            self._fieldDict[schema] = f
        return f, len(f)

    def __str__(self):
        repr = "oplmodel:\n"
        if self._filename is not None:
            repr += ("     mod file: {0}\n".format(self._filename))
        else:
            repr += ("     mod file: \n")
        repr += ("     {0:d} .dat files\n").format(len(self._datfiles))
        for d in self._datfiles:
            repr += ("         {0} input data file\n".format(d))
        repr += ("     {0:d} python structures\n").format(len(self._inputs))
        for k,v in iteritems(self._inputs):
            repr += ("         {0} custom input (pandas, sql, tuple lists)\n".format(k))
        return repr


    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.end()

    def end(self):
        self._inputs = None
        self._datfiles = None
        self._cplex_stats = None
        self._cplex_quality = None
        self._fieldDict = None
        self._env.end()


    def set_input(self, name, value = None):
        """
        Add an input IloTupleSet to OPL problem
        :param name: name of the input IloTupleSet to initialize or a .dat filename
        :param value: a list of tuples, a pandas dataframe, an iterable of iterable or None if a .dat filename is used
        :return: none
        """
        if value is not None:
            modelDef = self._opl.getModelDefinition()
            if modelDef.hasElementDefinition(name) is False:
                message = "{0} does not exist in the .mod file\n".format(name)
                raise(message)
            definition = modelDef.getElementDefinition(name)
            if definition.isExternalData() is False:
                message = "{0} is not an external ... data\n".format(name)
                raise Exception(message)
            if definition.isTupleSet() is False:
                message = "Only TupleSets are supported via doopl: {0} is not an external TupleSet.\n".format(name)
                raise Exception(message)

            self._inputs[name] = value
        else:
            self._datfiles.append(name)


    def __solve(self):
        if self._opl.isUsingCP():
            return self._opl.getCP().solve()
        else:
            return self._opl.getCplex().solve()

    @property
    def objective_value(self):
        """
        Retrieves the objective from the CPLEX or CPO engine.
        :return: the objective value
        """
        return self._get_obj_value()

    def _get_obj_value(self):
        if self._opl.isUsingCP():
            return self._opl.getCP().getObjValue()
        else:
            return self._opl.getCplex().getObjValue()

    def get_kpi(self, name):
        """
        Retrieves the value of a dexpr
        :param name: name of the dexpr
        :return: a floating point value
        """
        elt = None
        try:
            elt = self._opl.getElement(name)
        except:
            raise ValueError("{0} is not a valid OPL KPI".format(name))
        if elt.isDecisionExpression():
            return elt.asNum()
        else:
            raise ValueError("{0} is not a valid OPL KPI".format(name))

    def apply_ops_file(self, name):
        """
        Use this to add specific setting to OPL, CPLEX or CPO.
        :param name: name of the .ops file
        :return:
        """
        self._opl.applyOpsSettings(name)

    def setExportInternalData(self, name):
        self._opl.getSettings().setExportInternalData(name);
    def setExportExternalData(self, name):
        self._opl.getSettings().setExportExternalData(name);

    def use_profiler(self):
        """
        Use this method if you want OPL to display a profiling log.
        :return: 
        """
        settings = self._opl.getSettings()
        _profiler = IloOplProfiler(self._env)
        _profiler.setIgnoreUserSection(True)
        settings.setProfiler(_profiler)

    def __generate(self):
        try:
            if self._opl.isGenerated() is False:
                self._opl.getSettings().setSkipWarnNeverUsedElements(True)
                self._opl.getSettings().setWithNames(True)
                if len(self._inputs) != 0:
                    s = MyDataSource(self, self._inputs)
                    source = IloOplDataSource(s)
                    self._opl.addDataSource(source)
                if len(self._datfiles) != 0:
                    for v in self._datfiles:
                        d = IloOplDataSource(self._opl.getEnv(), v)
                        self._opl.addDataSource(d)
                if self._opl.hasMain():
                    self._opl.main()
                else:
                    self._opl.generate()
            return True
        except Exception:
            raise
        return False


    def run(self):
        """
        Use this method to generate and solve the problem.
        :return: True or False, depending on the solve engine status
        """
        try:
            if self.__generate():
                if self.__solve() is False:
                    return False
                self._opl.postProcess()
                settings = self._opl.getSettings()
                if settings.hasProfiler():
                    settings.getProfiler().printReport()
                return True
            else:
                raise ValueError("model was not generated")
        finally:
            self.flush_engine_logs()

    def run_seed(self, nb):
        """
        Will the run seed diagnosis.
        Can work only with models without main.
        For CPLEX, it can run only with MIP problems.
        :param nb: 
        :return: 
        """
        if self._opl.hasMain():
            raise ValueError("Model has main")
        if self._opl.isGenerated() is False:
            self._opl.generate()
        self._opl.runSeed(nb)

    def print_relaxation(self):
        """
        Displays the relaxations
        :return: the number of relaxation
        """
        if self.__generate():
            if self._opl.isUsingCP():
                raise ValueError("Relaxations are available only for CPLEX models")
            return self._opl._printRelaxation()
        else:
            raise ValueError("Can't generate the model to call relaxations")

    def print_conflict(self):
        """
        Displays the conflicts
        :return: the number of conflicts
        """
        if self.__generate():
            return self._opl._printConflict()
        else:
            raise ValueError("Can't generate the model to call conflicts")

    @property
    def cplex_quality(self):
        """
        Returns the quality stats of the CPLEX problem as a dict.
        :return: a dict { name => value }
        """
        return self._get_cplex_quality()

    def _get_cplex_quality(self):
        if self._cplex_quality is not None:
            return self._cplex_quality
        if self._opl.isUsingCP():
            raise ValueError("Cannot CPLEX specific method use with CPO");
        ret = OrderedDict()
        cplex = self._opl.getCplex()
        size = cplex._getQualityEnumSize()
        p_inf = float("inf")
        for i in range(size):
            if i != 10 and i != 11: # bug in the code/build or in CPLEX?
                name = cplex._getQualityEnumName(i)
                value = cplex._getQuality(i)
                if (value != p_inf):
                    ret[name] = value
        self._cplex_quality = ret
        return ret

    @property
    def cplex_stats(self):
        """
        Returns the CPLEX problem statistics as a dict {name : value}
        :return: a dict { name => value }
        """
        return self._get_cplex_stats()

    def _get_cplex_stats(self):
        """
        Returns the CPLEX problem statistics as a dict {name : value}
        :return:
        """
        if self._cplex_stats is not None:
            return self._cplex_stats
        if self._opl.isUsingCP():
            raise ValueError("Cannot CPLEX specific method use with CPO");
        ret = OrderedDict()
        cplex = self._opl.getCplex()
        ret["Niterations"] = cplex.getNiterations()
        ret["NbarrierIterations"] = cplex.getNbarrierIterations()
        ret["NsiftingIterations"] = cplex.getNsiftingIterations()
        ret["NsiftingPhaseOneIterations"] = cplex.getNsiftingPhaseOneIterations()
        ret["Ncols"] = cplex.getNcols()
        ret["Nrows"] = cplex.getNrows()
        ret["NQCs"] = cplex.getNQCs()
        ret["NSOSs"] = cplex.getNSOSs()
        ret["Nindicators"] = cplex.getNindicators()
        ret["NLCs"] = cplex.getNLCs()
        ret["NUCs"] = cplex.getNUCs()
        ret["NNZs"] = cplex.getNNZs()
        ret["NintVars"] = cplex.getNintVars()
        ret["NbinVars"] = cplex.getNbinVars()
        ret["NsemiContVars"] = cplex.getNsemiContVars()
        ret["NsemiIntVars"] = cplex.getNsemiIntVars()
        ret["BestObjValue"] = cplex.getBestObjValue()
        ret["IncumbentNode"] = cplex.getIncumbentNode()
        ret["NprimalSuperbasics"] = cplex.getNprimalSuperbasics()
        ret["NdualSuperbasics"] = cplex.getNdualSuperbasics()
        ret["NphaseOneIterations"] = cplex.getNphaseOneIterations()
        ret["Nnodes"] = cplex.getNnodes()
        ret["NnodesLeft"] = cplex.getNnodesLeft()
        ret["NcrossPPush"] = cplex.getNcrossPPush()
        ret["NcrossPExch"] = cplex.getNcrossPExch()
        ret["NcrossDPush"] = cplex.getNcrossDPush()
        ret["NcrossDExch"] = cplex.getNcrossDExch()
        ret["isPrimalFeasible"] = cplex.isPrimalFeasible()
        ret["isDualFeasible"] = cplex.isDualFeasible()
        ret["CplexStatus"] = cplex.getCplexStatus_asInt()

        if cplex.isMIP():
            ret["NMIPStarts"] = cplex.getNMIPStarts()
            ret["MIPRelativeGap"] = cplex.getMIPRelativeGap()
            ret["Cutoff"] = cplex.getCutoff()
        self._cplex_stats = ret
        return ret

    def get_table(self, name, as_pandas = True):
        """
        Retrieves an IloTupleSet as a pandas dataframe
        :param name: name of the IloTupleSet
        :return: a pandas dataframe
        """
        if self._is_tuple_set(name):
            elt = self._opl.getElement(name)
            return self.__getTupleSet(elt.asTupleSet(), as_pandas)
        raise ValueError("{0} is not a TupleSet".format(name))


    def __getTupleSet(self, set, as_pandas = True):
        tset = set
        schema = tset.getSchema()
        fields, size = self._getFields(schema)#._getColumnTypes()#_get_schema_types(schema)

        columns = []
        for i,type in enumerate(fields):
            if type == OPL_INTEGER:
                columns.append(tset.getIntColumnValues(i))
            elif type == OPL_FLOAT:
                columns.append(tset.getNumColumnValues(i))
            else:
                columns.append(tset.getSymbolColumnValues(i))


        rep = [tuple(i) for i in zip(*(c for c in columns))]
        columns = None

        if as_pandas is False:
            return rep

        def get_names(schem):
            names = list()
            if schem._hasSubTuple() is False:
                for i in range(0, schem.getSize()):
                    names.append(schem.getColumnName(i))
            else:
                for i in range(0, schem.getSize()):
                    if schem._isTuple(i):
                        sub = schema._getTupleColumn(i)
                        subNames = get_names(sub)
                        subName = sub.getName()
                        for i in subNames:
                            names.append(subName+"."+i)
                    else:
                        names.append(schem.getColumnName(i))
            return names

        names = get_names(schema)

        return pd.DataFrame(rep, columns=names)

    def export_model(self, name):
        """
        Exprts the model as LP/SAV/MPS for CPLEX or as .cpo for CPO.
        :param name:
        :return:
        """
        extension = name[-3:]
        if extension not in {"sav", ".lp", "cpo", "mps"}:
            raise("can't export: give a correct file engine extension")
        if self.__generate():
            if self._opl.isUsingCP():
                self._opl.getCP().exportModel(name)
            else:
                self._opl.getCplex().exportModel(name)
        else:
            raise("model was not generated")

    def mute(self):
        """
        Swtiches OPL/CPLEX/CPO into silent mode (no log).
        :return:
        """
        self._opl.mute()

    def unmute(self):
        """
        Swtiches OPL/CPLEX/CPO back to log mode.
        :return:
        """
        self._opl.unmute()

    def convert_all_intvars(self):
        """
        Converts all integer and boolean variables to floating point variables.
        :return:
        """
        self._opl.convertAllIntVars()

    def unconvert_all_intvars(self):
        """
        All variables which were moved from integer to float will get back to integer.
        :return:
        """
        self._opl.unconvertAllIntVars()


    @property
    def report(self):
        """
        Returns all the IloTupleSet from post processing section as a dict {name : pandas dataframe}
        :return: a dict { name => value }
        """
        return self._get_report()

    def _get_report(self):
        """
        Returns all the IloTupleSet from post processing section as a dict {name : pandas dataframe}
        :return: a dict
        """
        rep = dict()
        names = self._get_report_table_names()
        for n in names:
            rep[n] = self.get_table(n)
        return rep

    def compile(self, name):
        self.__generate()
        self._opl.compile(name)

    def redirect_engine_log(self, name):
        """
        Redirects the engine log to a file.
        """
        self.mute()
        self._opl._installEngineLog(name)

    def flush_engine_logs(self):
        self._opl._flushEngineLogs()

    @property
    def output_table_names(self):
        return self._get_report_table_names()

    def _get_report_table_names(self):
        """
        Returns all the IloTupleSet names from post processing section as a list of strings
        :return: a list
        """
        rep = []
        names = self._opl.getElementNamesInPostProcessing()
        for i in range(0, names.getSize()):
            name = names.get_String(i)
            elt = self._opl.getElement(name)
            if self._is_tuple_set(name):
                rep.append(elt.getName())
        return rep

    def _is_tuple_set(self,name):
        elt = None
        try:
            elt = self._opl.getElement(name)
        except:
            raise ValueError("Table {0} does not exist in the OPL model.".format(name))
        if elt.isDiscreteDataCollection():
            if elt.isDiscreteDataCollection():
                if elt.asDiscreteDataCollection().isTupleSet():
                    return True
        return False

    def _is_kpi(self,name):
        elt = self._opl.getElement(name)
        if elt.isDecisionExpression():
            return True
        return False

    def _to_sql(self,con, name):
        """
        Unsupported method to publish table in a database.
        The table must exist in the database, and will be cleared before the results are published.
        :param con: a SqlAlchemy connection
        :param name: the table to publish
        :return:
        """
        table = self.get_table(name, as_pandas=False)
        if con.has_table(name) is False:
            raise ValueError("Table {0} does not exist".format(name))
        else:
            query = "DELETE FROM {0:s}".format(name)
            con.execute(query)

        if (len(table)):
            size = len(table[0])
            wildcards = ','.join(['?'] * size)
            query = 'INSERT INTO {0:s} VALUES ({1:s})'.format(name, wildcards)
            con.execute(query, table)
            wildcards = None
        table = None

    def get_slacks(self, name):
        """
        Returns the slacks for a map of constraints.
        Works only if the "names" setting is kept on as in default.
        :param name: name of a Map element
        :return: a dict (name of element => value)
        """
        names = self._opl._getNames(name)
        slacks = self._opl._getSlacks(name)
        ret = {}
        for i in range(0, slacks.getSize()):
            ret[names.get_String(i)] = slacks.get_Num(i)
        names.end()
        slacks.end()
        return ret

    def get_reduced_costs(self, name):
        """
        Returns the slacks for a map of variables.
        Works only if the "names" setting is kept on as in default.
        :param name: name of a Map element
        :return: a dict (name of element => value)
        """
        names = self._opl._getNames(name)
        costs = self._opl._getReducedCosts(name)
        ret = {}
        for i in range(0, costs.getSize()):
            ret[names.get_String(i)] = costs.get_Num(i)
        names.end()
        costs.end()
        return ret

    def get_duals(self, name):
        """
        Returns the duals for a map of variables.
        Works only if the "names" setting is kept on as in default.
        :param name: nme of a Map element
        :return: a dict (name of element => value)
        """
        names = self._opl._getNames(name)
        duals = self._opl._getDuals(name)
        ret = {}
        for i in range(0, duals.getSize()):
            print(names.get_String(i))
            ret[names.get_String(i)] = duals.get_Num(i)
        names.end()
        duals.end()
        return ret

