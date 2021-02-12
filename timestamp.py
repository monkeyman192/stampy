from functools import wraps
import time
from typing import Union


REPORT_FUNC_VAL = "Function '{0}' took {1}s to run"
REPORT_FUNC_AVG = (
    "Function '{0}' was run {1} time(s) with an average run time of {2}s")
REPORT_DIFF_AVG = "Average time between '{0}' and '{1}' over {2} runs: {3}s"
REPORT_DIFF_VAL = "Time from '{0}' to '{1}': {2}s"
REPORT_NESTED_DIFF = (
    "Average time between '{0}' and '{1}' inside function '{2}' over {3} "
    "(={4}) repetitions: {5}s")

REPORT_TIMEFRAME = (
    "Function '{0}':\n"
    "\tTime run: {1}\n"
    "\tAverage run time: {2}\n"
)


class NoStampException(Exception):
    pass


class InvalidStampException(Exception):
    pass


# TODO: Have an formatted and non-formatted version?
def calc_averages(start_times: list, end_times: list, start_desc: str = None,
                  end_desc: str = None, func_name: str = None) -> str:
    avgs = []
    if len(start_times) == len(end_times):
        # Return the number of times run and the average amount of time
        # per run.
        avgs = [end_times[i] - start_times[i]
                for i in range(len(start_times))]
        if func_name:
            if len(avgs) > 1:
                return REPORT_FUNC_AVG.format(
                    func_name, len(avgs), sum(avgs) / len(avgs))
            elif len(avgs) == 1:
                return REPORT_FUNC_VAL.format(func_name, avgs[0])
        else:
            if len(avgs) > 1:
                return REPORT_DIFF_AVG.format(
                    start_desc, end_desc, len(avgs), sum(avgs) / len(avgs))
            elif len(avgs) == 1:
                return REPORT_DIFF_VAL.format(start_desc, end_desc, avgs[0])
    return avgs


class FunctionTimeFrame():
    """ An object to contain all the information about a particular set of
    timestamps within a function."""
    __slots__ = ('name', 'time_stamps')

    def __init__(self, func_name):
        self.name = func_name
        self.time_stamps = {}

    def stamp(self, key: Union[str, int]):
        _curr_time = time.time()
        if key not in self.time_stamps:
            self.time_stamps[key] = [_curr_time]
        else:
            self.time_stamps[key].append(_curr_time)

    @property
    def times_run(self) -> int:
        return len(self.time_stamps.get(-1, []))

    @property
    def average_runtime(self) -> float:
        start_times = self.time_stamps.get(0, [])
        end_times = self.time_stamps.get(-1, [])
        return (sum(end_times) - sum(start_times)) / self.times_run

    def runtime(self) -> str:
        start_times = self.time_stamps.get(0, [])
        end_times = self.time_stamps.get(-1, [])
        return calc_averages(start_times, end_times, func_name=self.name)

    def report(self) -> str:
        """ Return a nicely formatted report of the runtimes of this particular
        function. """
        return REPORT_TIMEFRAME.format(self.name,
                                       self.times_run,
                                       self.average_runtime)

    def __str__(self) -> str:
        return f"Time frame for {self.name} containing the timestamps {self.time_stamps}"


class Stamp():
    _stamps_cache = {}

    def __init__(self, name):
        self._name = name
        self._time_stamps = {}
        self._func_time_stamps = {}
        # TODO: do we need the function stack??
        self._func_stack = []
        self._func_deltas = {}
        self._reported_functions = set()

    def __new__(cls, name: str):
        """ Force the Stamps to be singleton-like. Ie. Any time you would try
        and instantiate another timestamp object with the same name it will
        find the existing one. This allows us to add timestamps across multiple
        files without issue. """
        if not cls._stamps_cache.get(name):
            cls._stamps_cache[name] = super(Stamp, cls).__new__(cls)
        return cls._stamps_cache[name]

    def add_func_deltas(self, func_name: str, deltas: list):
        self._func_deltas[func_name] = deltas

    def add_reported_function(self, func_name: str):
        self._reported_functions.add(func_name)

    @classmethod
    def get_instance(cls, name=None) -> 'Stamp':
        """ Return an instance of the class with the given name.
        If no name is specified it will check to see if there is only one
        instance in existence.
        If so this is returned, otherwise an error is raised.
        """
        if name:
            try:
                return cls._stamps_cache[name]
            except KeyError:
                raise NoStampException
        else:
            stamp_names = list(cls._stamps_cache.keys())
            if len(stamp_names) == 1:
                return cls._stamps_cache[stamp_names[0]]

    def enter_function(self, func_name: str):
        if self._func_stack:
            # If the specified function name is not the latest in the stack,
            # add it.
            if self._func_stack[-1] != func_name:
                self._func_stack.append(func_name)
        else:
            self._func_stack.append(func_name)
        # Also add the start time of the function to the time stamps
        func_tf = self._func_time_stamps.get(func_name,
                                             FunctionTimeFrame(func_name))
        func_tf.stamp(0)
        if func_name not in self._func_time_stamps:
            self._func_time_stamps[func_name] = func_tf

    def exit_function(self):
        """ Remove the most recent function from the stack. """
        if self._func_stack:
            func_name = self._func_stack.pop(-1)
        # Also add the start time of the function to the time stamps
        func_tf = self._func_time_stamps.get(func_name,
                                             FunctionTimeFrame(func_name))
        func_tf.stamp(-1)

    def _stamp(self, key: Union[str, int]):
        _curr_time = time.time()
        if key not in self._time_stamps:
            self._time_stamps[key] = [_curr_time]
        else:
            self._time_stamps[key].append(_curr_time)

    def stamp(self, desc: str):
        if not isinstance(desc, str):
            raise InvalidStampException("Description must be a string")
        # TODO: fix this to allow multiply nested functions...
        if self._func_stack:
            self._func_time_stamps[self._func_stack[-1]].stamp(desc)
        else:
            self._stamp(desc)

    def func_runtime(self, func_name: str) -> str:
        tf = self._func_time_stamps.get(func_name)
        if tf:
            return tf.runtime()
        else:
            return 'No function exists with this name...'

    def difference(self, start: str, end: str, func_name: str = None) -> str:
        if func_name:
            start_times = self._time_stamps.get((func_name, start), [])
            end_times = self._time_stamps.get((func_name, end), [])
        else:
            start_times = self._time_stamps.get(start, [])
            end_times = self._time_stamps.get(end, [])
        return calc_averages(start_times, end_times, start, end)

    def report(self):
        """ Return a nicely formatted report of the running times. """
        for fname in self._reported_functions:
            print(self._func_time_stamps[fname].report())


def report(stamp_name=None, deltas=[]):
    """ Decorator for a function to include timings in the report.

    Parameters
    ----------
    stamp_name
        In the case of multiple Stamp objects, specify the name here so that it
        is reported correctly.
    deltas
        A list of the descriptions that are to be logged in the report.
        Any description included that doesn't exist within the scope of this
        function definition will be ignore.
        If the value is 'ALL' TODO: add a constant? timestamp.ALL??
        then all stamps in the function definition will be included.

    """
    def decorated_report(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            fname = func.__qualname__
            ts = Stamp.get_instance(stamp_name)
            ts.add_reported_function(fname)
            ts.enter_function(fname)
            if deltas:
                ts.add_func_deltas(fname, deltas)
            val = func(*args, **kwargs)
            ts.exit_function()
            return val
        return wrapper
    return decorated_report


if __name__ == "__main__":
    ts = Stamp('test')

    @report()
    def f(x):
        for _ in range(x):
            ts.stamp('start')
            time.sleep(0.1)
            ts.stamp('end')

    ts.stamp('before function')
    for i in range(4):
        f(5)
    ts.stamp('after function')

    print(ts._func_time_stamps['f'])
    print('-----------------')
    print(ts.func_runtime('f'))
    print('-----------------')
    print(ts.difference('before function', 'after function'))
    print('-----------------')
    print(ts.report())
