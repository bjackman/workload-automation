import csv

from wa import ResultProcessor, Parameter
from wa.framework.exception import ConfigError
from wa.utils.types import list_of_strings


class CsvReportProcessor(ResultProcessor):

    name = 'csv'
    description = """
    Creates a ``results.csv`` in the output directory containing results for
    all iterations in CSV format, each line containing a single metric.

    """

    parameters = [
        Parameter('use_all_classifiers', kind=bool, default=False,
                  global_alias='use_all_classifiers',
                  description="""
                  If set to ``True``, this will add a column for every classifier
                  that features in at least one collected metric.

                  .. note:: This cannot be ``True`` if ``extra_columns`` is set.

                  """),
        Parameter('extra_columns', kind=list_of_strings,
                  description="""
                  List of classifiers to use as columns.

                   .. note:: This cannot be set if ``use_all_classifiers`` is
                             ``True``.

                  """),
    ]

    def validate(self):
        super(CsvReportProcessor, self).validate()
        if self.use_all_classifiers and self.extra_columns:
            msg = 'extra_columns cannot be specified when '\
                  'use_all_classifiers is True'
            raise ConfigError(msg)

    def initialize(self):
        self.results_so_far = []  # pylint: disable=attribute-defined-outside-init
        self.artifact_added = False

    def process_job_output(self, output, target_info, run_output):
        self.results_so_far.append(output)
        self._write_results(self.results_so_far, run_output)
        if not self.artifact_added:
            run_output.add_artifact('run_result_csv', 'results.csv', 'export')
            self.artifact_added = True

    def process_run_result(self, output, target_info):
        self.results_so_far.append(output.result)
        self._write_results(self.rsults_so_far, output)
        if not self.artifact_added:
            output.add_artifact('run_result_csv', 'results.csv', 'export')
            self.artifact_added = True

    def _write_results(self, results, output):
        if self.use_all_classifiers:
            classifiers = set([])
            for result in results:
                for metric in result.metrics:
                    classifiers.update(metric.classifiers.keys())
            extra_columns = list(classifiers)
        elif self.extra_columns:
            extra_columns = self.extra_columns
        else:
            extra_columns = []

        outfile = output.get_path('results.csv')
        with open(outfile, 'wb') as wfh:
            writer = csv.writer(wfh)
            writer.writerow(['id', 'workload', 'iteration', 'metric', ] +
                            extra_columns + ['value', 'units'])

            for o in results:
                header = [o.id, o.label, o.iteration]
                for metric in o.result.metrics:
                    row = (header + [metric.name] +
                           [str(metric.classifiers.get(c, ''))
                            for c in extra_columns] +
                           [str(metric.value), metric.units or ''])
                    writer.writerow(row)
