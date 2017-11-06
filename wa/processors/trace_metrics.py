#    Copyright 2017 ARM Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

try:
    import trappy
    import millhouse
    libs_available = True
except ImportError:
    libs_available = False
else:
    from millhouse import TraceAnalyzer, MissingTraceEventsError
    from trappy import FTrace
    from trappy.stats.Topology import Topology

from wa import ResultProcessor
from wa.framework.exception import ResultProcessorError

# TODO: Should find a way to hook into the AFTER_RUN_INIT signal (or something),
# and use that to check that if we were enabled, so was trace-cmd

class TraceMetricsProcessor(ResultProcessor):
    name = 'trace-metrics'

    description = """ TODO """

    events = ['cpu_idle', 'cpu_frequency']

    def validate(self):
        if not libs_available:
            raise ResultProcessorError(
                'The trace-metrics result processor requires that the trappy '
                'and millhouse libraries are installed.')

    def process_job_output(self, job_output, target_info, run_output):
        trace_path = job_output.get_artifact_path('trace-cmd-bin')
        if not trace_path:
            self.logger.error('No trace-cmd-bin artifact found. '
                              'Is the trace-cmd instrument enabled & working?')
            return

        topology = self._get_topology(target_info)

        ftrace = FTrace(trace_path, scope='custom', events=self.events)
        analyzer = TraceAnalyzer(ftrace,
                                 topology=topology,
                                 cpufreq_domains=target_info.cpufreq_domains)

        for cls in MetricGroup.__subclasses__():
            try:
                cls(analyzer, job_output).process_metrics()
            except MissingTraceEventsError as e:
                self.logger.warning('Disabling metric group "{}": {}'
                                    .format(str(e)))

    def _get_topology(self, target_info):
        core_cluster_idxs = target_info.platform.core_clusters
        if core_cluster_idxs:
            # Convert list of cluster indexes to list of cluster members
            # (i.e. [0, 0, 1, 1] -> [[0, 1], [2, 3]])
            #
            # Start with an empty list for each cluster
            clusters = [[] for _ in range(max(core_cluster_idxs) + 1)]
            # Now append each CPU ID to the cluster it belongs in
            for cpu, cluster_idx in enumerate(core_cluster_idxs):
                clusters[cluster_idx].append(cpu)

            return Topology(clusters)
        else:
            return None

class MetricGroup(object):
    def __init__(self, analyzer, output):
        self.analyzer = analyzer
        self.output = output
        self.topology = analyzer.topology

    def add_metric(self, name, value, units=None):
        name = 'trace:{}'.format(name)
        self.output.add_metric(name, value, units)

    def add_coregroup_metric(self, group, name, value, units=None):
        name = '{}_{}'.format(name, '-'.join(str(c) for c in group))
        self.add_metric(name, value, units)

class WakeupMetricGroup(MetricGroup):
    name = 'cpu-wakeups'

    def process_metrics(self):
        wakeup_df = self.analyzer.idle.event.cpu_wakeup()

        if self.topology:
            for cluster in self.topology.get_level('cluster'):
                self.add_coregroup_metric(
                    cluster, 'cpu_wakeups',
                    len(wakeup_df[wakeup_df['cpu'].isin(cluster)]))

        self.add_metric('cpu_wakeups', len(wakeup_df))


class FrequencyMetricGroup(MetricGroup):
    name = 'frequency'

    def process_metrics(self):
        _df = self.analyzer.cpufreq.stats.frequency_residency()
        print _df
        for (cpu, kind), df in _df.iteritems():
            # frequency_residency just indexes with a single CPU - find that
            # CPU's domain so we can use that to name the metric
            [domain] = [d for d in self.analyzer.cpufreq_domains if cpu in d]

            print df
            df = df.reset_index()

            avg_freq = ((df['frequency'] * df[cpu][kind]).sum()
                        / df[cpu][kind].sum())
            self.add_coregroup_metric(
                domain, 'avg_freq_{}'.format(kind), avg_freq, 'Hz')
