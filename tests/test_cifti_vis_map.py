#!/usr/bin/env python3
import unittest
import importlib
import random

from unittest.mock import patch

vis_map = importlib.import_module('ciftify.bin.cifti_vis_map')

class TestUserSettings(unittest.TestCase):

    temp = '/tmp/fake_temp_dir'
    palette = 'PALETTE-NAME'

    def test_snap_set_to_none_when_in_index_mode(self):
        args = self.get_default_arguments()
        args['index'] = True
        args['<map-name>'] = 'some-map-name'

        cifti = vis_map.UserSettings(args, self.temp).snap

        assert cifti is None

    @patch('ciftify.utils.run')
    def test_snap_set_to_original_cifti_when_in_cifti_snaps_mode(self,
            mock_docmd):
        cifti_path = '/some/path/my_map.dscalar.nii'
        args = self.get_default_arguments()
        args['cifti-snaps'] = True
        args['<map.dscalar.nii>'] = cifti_path

        cifti = vis_map.UserSettings(args, self.temp).snap

        assert cifti == cifti_path
        assert mock_docmd.call_count == 0

    @patch('ciftify.utils.run')
    def test_snap_is_nifti_converted_to_cifti_in_nifti_snaps_mode(self,
            mock_docmd):
        args = self.get_default_arguments()
        args['nifti-snaps'] = True
        args['<map.nii>'] = '/some/path/my_map.nii'

        cifti = vis_map.UserSettings(args, self.temp).snap

        # Expect only ciftify-a-nifti needs to be run
        assert mock_docmd.call_count == 1
        # Extract first (only) call, then arguments to call, then command list.
        assert 'ciftify_vol_result' in mock_docmd.call_args_list[0][0][0]

    @patch('ciftify.utils.run')
    def test_palette_changed_when_option_set_in_nifti_snaps_mode(self,
            mock_docmd):
        args = self.get_default_arguments()
        args['nifti-snaps'] = True
        args['<map.nii>'] = '/some/path/my_map.nii'
        args['--colour-palette'] = self.palette

        vis_map.UserSettings(args, self.temp)

        assert self.palette_changed(mock_docmd.call_args_list)

    @patch('ciftify.utils.run')
    def test_palette_not_changed_when_option_unset_in_nifti_snaps_mode(self,
            mock_docmd):
        args = self.get_default_arguments()
        args['nifti-snaps'] = True
        args['<map.nii>'] = '/some/path/my_map.nii'

        vis_map.UserSettings(args, self.temp)

        assert not self.palette_changed(mock_docmd.call_args_list,
                strict_check=True)

    @patch('ciftify.utils.run')
    def test_palette_changed_when_option_set_in_cifti_snaps_mode(self,
            mock_docmd):
        args = self.get_default_arguments()
        args['cifti-snaps'] = True
        args['<map.dscalar.nii>'] = '/some/path/my_map.dscalar.nii'
        args['--colour-palette'] = self.palette

        vis_map.UserSettings(args, self.temp)

        assert self.palette_changed(mock_docmd.call_args_list)

    @patch('ciftify.utils.run')
    def test_palette_not_changed_when_option_unset_in_cifti_snaps_mode(self,
            mock_docmd):
        args = self.get_default_arguments()
        args['cifti-snaps'] = True
        args['<map.dscalar.nii>'] = '/some/path/my_map.dscalar.nii'

        vis_map.UserSettings(args, self.temp)

        assert not self.palette_changed(mock_docmd.call_args_list,
                strict_check=True)

    @patch('ciftify.utils.run')
    def test_nifti_resampled_during_conversion_to_cifti_when_resample_nifti_set(
            self, mock_docmd):
        args = self.get_default_arguments()
        args['nifti-snaps'] = True
        nifti = '/some/path/my_map.nii'
        args['<map.nii>'] = nifti
        args['--resample-nifti'] = True

        settings = vis_map.UserSettings(args, self.temp)

        # Reset mock_docmd to clear call_args_list
        mock_docmd.reset_mock()
        settings._UserSettings__convert_nifti(nifti)
        args_list = mock_docmd.call_args_list[0][0][0]

        assert '--resample-nifti' in args_list

    @patch('ciftify.utils.run')
    def test_nifti_not_resampled_when_resample_nifti_unset(self, mock_docmd):
        args = self.get_default_arguments()
        args['nifti-snaps'] = True
        nifti = '/some/path/my_map.nii'
        args['<map.nii>'] = nifti

        settings = vis_map.UserSettings(args, self.temp)

        # Reset mock_docmd to clear call_args_list
        mock_docmd.reset_mock()
        settings._UserSettings__convert_nifti(nifti)
        args_list = mock_docmd.call_args_list[0][0][0]

        assert '--resample-nifti' not in args_list

    def get_default_arguments(self):
        # arguments 'stub' - acts as a template to be modified by tests
        arguments = {'cifti-snaps': False,
                     '<map.dscalar.nii>': None,
                     'nifti-snaps': False,
                     '<map.nii>': None,
                     'index': False,
                     '<map-name>': None,
                     '<subject>': 'subject_id',
                     '--qcdir': '/some/path/qc',
                     '--roi-overlay': None,
                     '--hcp-data-dir': '/some/path/hcp',
                     '--subjects-filter': None,
                     '--colour-palette': None,
                     '--output-dscalar': None,
                     '--resample-nifti': False}
        return arguments

    def palette_changed(self, call_args_list, strict_check=False):
        changed = False
        for call in call_args_list:
            arg_list = call[0][0]
            if '-palette-name' in arg_list:
                # If strict_check any changes to the palette will be caught
                if strict_check or self.palette in arg_list:
                    changed = True
        return changed
