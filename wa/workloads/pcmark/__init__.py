# SPDX-License-Identifier: Apache-2.0
#
# Copyright (C) 2017, Arm Limited and contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import time

from wa import Parameter, Workload
from wa.framework.exception import WorkloadError

REGEXPS = {
    'start'  : '.*START.*com.futuremark.pcmark.android.benchmark',
    'end'    : '.*onWebViewReady.*view_scoredetails.html',
    'result' : '.*received result for correct code, result file in (?P<path>.*\.zip)',
    'score'  : '\s*<result_Pcma(?P<name>.*)Score>(?P<score>[0-9]*)<'
}

class PcMark(Workload):
    """
    Android PCMark workload

    TODO: This isn't a proper WA workload! It requires that the app is already
    installed set up like so:

    - Install the APK from http://www.futuremark.com/downloads/pcmark-android.apk
    - Open the app and hit "install"

    """
    name = 'pcmark'

    package  = 'com.futuremark.pcmark.android.benchmark'
    activity = 'com.futuremark.gypsum.activity.SplashPageActivity'

    package_names = ['com.google.android.youtube']
    action = 'android.intent.action.VIEW'

    parameters = [
        Parameter('test', default='work', allowed_values=['work'],
                  description='PCMark sub-benchmark to run'),
    ]

    def initialize(self, context):
        super(PcMark, self).initialize(context)

        if not self.target.is_installed(self.package):
            raise WorkloadError('Not installed') # TODO instruccies

        path = ('/storage/sdcard0/Android/data/{}/files/dlc/pcma-workv2-data'
                .format(self.package))
        if not self.target.file_exists(path):
            raise WorkloadError('Not installed') # TODO INSTRUCCIES

    def setup(self, context):
        super(PcMark, self).setup(context)

        self.command = 'am start -n {}/{}'.format(self.package, self.activity)

        self.target.execute('am kill-all')  # kill all *background* activities

        # Move to benchmark run page
        self.target.execute('input keyevent KEYCODE_TAB')
        time.sleep(5)

        self.monitor = self.target.get_logcat_monitor()
        self.monitor.start()

    def run(self, context):
        self.target.execute('input keyevent KEYCODE_ENTER')
        # Wait for page animations to end
        time.sleep(10)

        [self.output] = self.monitor.wait_for(REGEXPS['result'], timeout=600)

    def update_output(self, context):
        remote_zip_path = re.match(REGEXPS['result'], self.output).group('path')
        local_zip_path = os.path.join(context.output_directory,
                                      self.target.path.basename(remote_archive))
        self.target.pull(remote_zip_path, local_zip_path)

    def teardown(self, context):
        super(PcMark, self).teardown(context)

        self.target.execute('am force-stop {}'.format(self.package))

        self.monitor.stop()
        # TODO: can we read and restore the previous orientation?
        self.target.screen.set_orientation(auto=True);

