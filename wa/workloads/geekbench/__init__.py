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
import time
from zipfile import ZipFile

from wa import Parameter, Workload, ApkWorkload
from wa.framework.exception import WorkloadError

# Regexps for benchmark synchronization
REGEXPS = {
    'start': r'ActivityManager: Start.* com.primatelabs.geekbench',
    'end':   r'GEEKBENCH_RESULT: (?P<results_file>.+)',
}

class Geekbench(ApkWorkload):

    name = 'geekbench'
    description = """
    TODO
    """

    versions = ['4.0.1']
    activity = '.HomeActivity'
    package = 'com.primatelabs.geekbench'

    parameters = [
        Parameter('version', default=versions[0], allowed_values=versions, override=True),
    ]

    def initialize(self, context):
        super(Geekbench, self).initialize(context)

        # # Need root to get results database
        # if not self.target.is_rooted:
        #     raise WorkloadError('Geekbench workload requires device to be rooted')

    def setup(self, context):
        super(Geekbench, self).setup(context)
        self.monitor = self.target.get_logcat_monitor(REGEXPS.values())
        self.monitor.start()

        self.target.execute('input keyevent KEYCODE_MENU')
        self.target.execute('input keyevent KEYCODE_BACK')

        self.target.screen.set_orientation(portrait=True)
        self.target.execute('am start -n {}/{}'.format(self.package, self.activity))

        time.sleep(1)
        # Accept EULA
        for i in range(2):
            self.target.execute('input keyevent KEYCODE_TAB')
        self.target.execute('input keyevent KEYCODE_ENTER')

        # Select the 'run benchmark' button (dont' press it yet)
        for i in range(4):
            self.target.execute('input keyevent KEYCODE_TAB')

    def run(self, context):
        # Press the 'run benchmark' button
        self.target.execute('input keyevent KEYCODE_ENTER')
        # All we need to do is
        # - start the activity,
        # - pull the result database file.

        self.monitor.wait_for(REGEXPS['start'])
        print 'started'

        self.monitor.wait_for(REGEXPS['end'], timeout=600)

    def teardown(self, context):
        super(Geekbench, self).teardown(context)
        self.monitor.stop()

    # def extract_results(self, context):
    #     # TODO make these artifacts where they should be
    #     super(Geekbench, self).extract_results(context)
    #     host_db_path =  os.path.join(context.output_directory,
    #                                  'BenchmarkResults.sqlite')
    #     self.target.pull(self.target_db_path, host_db_path, as_root=True)

    #     columns = ['_id', 'name', 'run_id', 'iteration', 'total_duration', 'jank_frame']
    #     jank_frame_idx = columns.index('jank_frame')
    #     query = 'SELECT {} FROM ui_results'.format(','.join(columns))
    #     conn = sqlite3.connect(os.path.join(host_db_path))

    #     csv_path = os.path.join(context.output_directory, 'jankbench_frames.csv')
    #     jank_frames = 0
    #     with open(csv_path, 'wb') as f:
    #         writer = csv.writer(f)
    #         writer.writerow(columns)
    #         for db_row in conn.execute(query):
    #             writer.writerow(db_row)
    #             if int(db_row[jank_frame_idx]):
    #                 jank_frames += 1

    #     context.add_metric('jankbench_jank_frames', jank_frames,
    #                        lower_is_better=True)



