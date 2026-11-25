import argparse
import contextlib
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import run_baiqi_remote_review as review


class RemoteQueueTimeoutTest(unittest.TestCase):
    def test_cancel_own_queued_job_after_deadline(self):
        args = argparse.Namespace(service_url='http://render.example', queue_timeout=60,
                                  stall_timeout=120, donor=None, cc0_control=None)
        params = {'cases': ['arms_forward'], 'timeout_seconds': 1800}
        responses = [
            {'ready': True, 'accepting_jobs': True},
            {'data': [{'id': 'blender-review', 'configured': True}]},
            {'job_id': 'render_owned'},
            {'status': 'queued'},
        ]
        with tempfile.TemporaryDirectory() as folder:
            with (
                patch.object(review, 'inputs_zip', side_effect=lambda file, *_: file.write_bytes(b'zip')),
                patch.object(review, 'response_json', side_effect=responses),
                patch.object(review, 'request', side_effect=lambda *_, **__: contextlib.closing(BytesIO())) as request,
                patch.object(review.time, 'monotonic', side_effect=[100., 161.]),
            ):
                with self.assertRaisesRegex(TimeoutError, 'queue exceeded'):
                    review.run_remote(args, params, {}, Path(folder))
        request.assert_called_with('http://render.example', '/v1/render/jobs/render_owned',
                                   method='DELETE', timeout=3)


if __name__ == '__main__':
    unittest.main()
