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

import re
import time

from wa import ApkWorkload, Parameter
from devlib.utils.android import grant_app_permissions

# Regexps for benchmark synchronization

REGEXPS = {
    'start'    : '.*Displayed com.google.android.exoplayer2.demo/.PlayerActivity',
    'duration' : '.*period \[(?P<duration>[0-9]+.*)\]',
    'end'      : '.*state \[.+, .+, E\]'
}

class ExoPlayer(ApkWorkload):
    """
    Android ExoPlayer workload

    Exoplayer sources: https://github.com/google/ExoPlayer

    The 'demo' application is used by this workload.
    It can easily be built by loading the ExoPlayer sources
    into Android Studio

    Expected apk is 'demo-noExtensions-debug.apk'

    Version r2.4.0 built from commit d979469 is known to work
    """

    name = 'exoplayer'

    versions = ["2.4.0"]
    action = 'com.google.android.exoplayer.demo.action.VIEW'

    parameters = [
        Parameter('package_name', default='com.google.android.exoplayer2.demo', override=True),
        Parameter('version', allowed_values=versions, default=versions[-1], override=True),
        Parameter(name='media_file',
                  # TODO mandatory params not working??
                  mandatory=True,
                  # default='/data/local/tmp/bbb_sunflower_1080p_30fps_normal.mp4',
                  description='Video file to play'),
        Parameter('from_device', default=False, description='Whether file to play is already on the device'),
        Parameter('play_duration_s', kind=int,
                  description='If set, maximum duration (seconds) of the media playback')
    ]

    def initialize(self, context):
        super(ExoPlayer, self).initialize(context)
        # Grant app all permissions
        grant_app_permissions(self.target, self.package)

    def setup(self, context):
        # The superclass calls self.apk.setup here, which starts the
        # activity. We don't want to do that until the run phase.
        self.apk.initialize_package(context)
        self.target.execute('am kill-all')  # kill all *background* activities
        self.target.clear_logcat()
        time.sleep(self.loading_time)

        # TODO: use ResourceGetter or something
        # Check media file exists
        if self.from_device and not self.target.file_exists(self.media_file):
            raise RuntimeError('Cannot find "{}" on target'.format(self.media_file))
        elif not self.from_device and not os.path.isfile(self.media_file):
            raise RuntimeError('Cannot find "{}" on host'.format(self.media_file))

        # Handle media file location
        if not self.from_device:
            self.remote_file = self.target.path.join(
                self.target.working_directory,
                os.path.basename(self.media_file)
            )

            self.logger.info('Pushing media file to device...')
            self.target.push(
                self.media_file,
                remote_file,
                timeout = 60
            )
            self.logger.info('Media file transfer complete')
        else:
            self.remote_file = self.media_file

        # Prepare logcat monitor
        self.monitor = self.target.get_logcat_monitor(REGEXPS.values())
        self.monitor.start()

    def run(self, context):
        play_cmd = 'am start -a {} -d "file://{}"'.format(self.action, self.remote_file)
        self.logger.debug(play_cmd)
        self.target.execute(play_cmd)

        self.monitor.wait_for(REGEXPS['start'])
        self.logger.info('Playing media file')

        line = self.monitor.wait_for(REGEXPS['duration'])[0]
        media_duration_s = int(round(float(re.search(REGEXPS['duration'], line)
                                   .group('duration'))))

        self.logger.info('Media duration is {} seconds'.format(media_duration_s))

        if self.play_duration_s and self.play_duration_s < media_duration_s:
            self.logger.info('Waiting {} seconds before ending playback'
                           .format(self.play_duration_s))
            time.sleep(self.play_duration_s)
        else:
            self.logger.info('Waiting for playback completion ({} seconds)'
                           .format(media_duration_s))
            self.monitor.wait_for(REGEXPS['end'], timeout = media_duration_s + 30)

        self.logger.info('Media file playback completed')

    def teardown(self, context):
        self.monitor.stop()
        super(ExoPlayer, self).teardown(context)

        # Remove file if it was pushed
        if not self.from_device:
            self.target.remove(self.remote_file)
