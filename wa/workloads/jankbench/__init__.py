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

import os
import re
import subprocess
import threading
import select

from wa import Parameter, ApkWorkload
from wa.framework.exception import WorkloadError

class Jankbench(ApkWorkload):

    name = 'jankbench'
    description = """
    Google's Jankbench benchmark.

    Jankbench simulates user interaction with Android UI components and records
    frame rendering times and 'jank' (rendering discontinuity) in an SQLite
    database. This  is believed to be a good proxy for the smoothness of user
    experience.

    Does not report any score but simply dumps a JankbenchResults.sqlite file in
    the output directory. This database contains a table 'ui_results' with a row
    for each frame, showing its rendering time in ms in the 'total_duration'
    column, and whether or not it was a jank frame in the 'jank_frame' column.
    """

    versions = ['1.0']
    activity = '.app.RunLocalBenchmarksActivity'
    package = 'com.android.benchmark'

    target_db_path = '/data/data/{}/databases/BenchmarkResults'.format(package)

    benchmark_ids = {
        'list_view'         : 0,
        'image_list_view'   : 1,
        'shadow_grid'       : 2,
        'low_hitrate_text'  : 3,
        'high_hitrate_text' : 4,
        'edit_text'         : 5,
    }

    parameters = [
        Parameter('benchmark',
                  default=benchmark_ids.keys()[0], allowed_values=benchmark_ids.keys(),
                  description='Which Jankbench sub-benchmark to run'),
        Parameter('run_timeout', kind=int, default=10 * 60,
                  description="""
                  Timeout for workload execution. The workload will be killed if it hasn't completed
                  within this period. In seconds.
                  """),
        Parameter('times', kind=int, default=1, constraint=lambda x: x > 0,
                  description=('Specifies the number of times the benchmark will be run in a "tight '
                               'loop", i.e. without performing setup/teardown in between.')),
    ]

    def initialize(self, context):
        super(Jankbench, self).initialize(context)

        # Need root to get results database
        if not self.target.is_rooted:
            raise WorkloadError('Jankbench workload requires device to be rooted')

    def setup(self, context):
        super(Jankbench, self).setup(context)
        self.monitor = JbRunMonitor(self.target, self.logger)
        self.monitor.start()

        self.command = (
            'am start -n com.android.benchmark/.app.RunLocalBenchmarksActivity '
            '--eia com.android.benchmark.EXTRA_ENABLED_BENCHMARK_IDS {0} '
            '--ei com.android.benchmark.EXTRA_RUN_COUNT {1}'
        ).format(self.benchmark_ids[self.benchmark], self.times)


    # def launch_package(self):
    #     # Unlike with most other APK workloads, we're invoking the use case
    #     # directly by starting the activity with appropriate parameters on the
    #     # command line during execution, so we dont' need to start activity
    #     # during setup.
    #     pass

    def run(self, context):
        # All we need to do is
        # - start the activity,
        # - then use the JbRunMonitor to wait until the benchmark reports on
        #   logcat that it is finished,
        # - pull the result database file.

        result = self.target.execute(self.command)
        print result
        if 'FAILURE' in result:
            raise WorkloadError(result)
        else:
            self.logger.debug(result)
        self.monitor.wait_for_run_end(self.run_timeout)

    def extract_results(self, context):
        super(Jankbench, self).extract_results(context)
        host_db_path =  os.path.join(context.output_directory,
                                     'BenchmarkResults.sqlite')
        self.target.pull(self.target_db_path, host_db_path, as_root=True)

# TODO: Use logcat monitor from devlib
class JbRunMonitor(threading.Thread):

    # Regexps for benchmark synchronization
    start_re = re.compile(
        r'.*ActivityManager: START.*'
        'cmp=com.android.benchmark/.app.RunLocalBenchmarksActivity.*'
    )
    count_re = re.compile(
        '.*System.out: iteration: (?P<iteration>[0-9]+).*'
    )
    metrics_re = re.compile(
        r'.*System.out: Mean: (?P<mean>[0-9\.]+)\s+JankP: (?P<junk_p>[0-9\.]+)\s+'
        'StdDev: (?P<std_dev>[0-9\.]+)\s+Count Bad: (?P<count_bad>[0-9]+)\s+'
        'Count Jank: (?P<count_junk>[0-9]+).*'
    )
    done_re = re.compile(
        r'.*I BENCH\s+:\s+BenchmarkDone!.*'
    )

    daemon = True

    def __init__(self, target, logger):
        super(JbRunMonitor, self,).__init__()
        self.target = target
        self.logger = logger

        self.run_ended = threading.Event()
        self.stop_event = threading.Event()

        # Not using clear_logcat() because command collects directly, i.e. will
        # ignore poller.
        self.target.execute('logcat -c')

        cmd = ['logcat', 'ActivityManager:*', 'System.out:I', '*:S', 'BENCH:*']
        if self.target.adb_name:
            self.command = ['adb', '-s', str(self.target.adb_name)] + cmd
        else:
            self.command = ['adb'] + cmd

    def _handle_line(self, line):
        match = self.start_re.match(line)
        if match:
            self.logger.info('Detected Jankbench start')
            return

        match = self.metrics_re.match(line)
        if match:
            self.logger.info('Detected Jankbench metrics: {}'.format(match.groups()))
            return

        match = self.done_re.match(line)
        if match:
            self.logger.info('Detected Jankbench end')
            self.run_ended.set()
            return

    def run(self):
        proc = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        while not self.stop_event.is_set():
            if self.run_ended.is_set():
                self.target.sleep(2)
            else:
                ready, _, _ = select.select([proc.stdout, proc.stderr], [], [], 2)
                if ready:
                    self._handle_line(ready[0].readline())

    def stop(self):
        self.stop_event.set()
        self.join()

    def wait_for_run_end(self, timeout):
        self.run_ended.wait(timeout)
        self.run_ended.clear()

