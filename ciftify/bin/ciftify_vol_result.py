#!/usr/bin/env python3
"""
Projects a result (or atlas) in nifti space to a surface and subcortical masks.

Usage:
  ciftify_vol_result [options] <subject> <vol.nii.gz> <output.dscalar.nii>

Arguments:
    <subject>              The subject ID for the surfaces to project to.
    <vol.nii.gz>           Nifty volume to project to cifti space
    <output.dscalar.nii>   Output dscalar.nii image

Options:
  --ciftify-work-dir PATH  The directory for HCP subjects (overrides
                           CIFTIFY_WORKDIR/ HCP_DATA enivironment variables)
  --integer-labels         The nifti input file contains integer label values
  --surface-vol NII        Specify a separate volume for surface projection than <vol.nii.gz>
  --subcortical-vol NII    Specify a separate volume for subcortical masks than <vol.nii.gz>
  --dilate mm              Run cifti-dilate with a specified mm
  --HCP-Pipelines          Indicates that the surfaces were generated by the HCP-Pipelines
  --HCP-MSMAll             Project to the MSMAll surface (instead of '32k_fs_LR', only works for HCP subjects)
  --resample-nifti         Use this argument to resample voxels 2x2x2 before projecting
  --hcp-data-dir PATH      DEPRECATED, use --ciftify-work-dir instead
  --debug                  Debug logging in Erin's very verbose style
  -n,--dry-run             Dry run
  -h,--help                Print help

DETAILS
This projects the nifti data to the surfaces from the MNINonLinear/32k_fs_LR space in hcp
for a given subject (the space used for fMRI analysis). This assumes that the HCP_DATA
folder was created with ciftify_recon_all. If the HCP_DATA was created using the
HCP pipelines (for example the HCP-dataset), use '--HCP-subject' option.

The '--surface-vol' and '--subcortical-vol' options were added so that you can specify
separate input nifty volumes for masks one the surface and for subcortical space.
(For example, so that a large hippocampus cluster is not projected to the nearby cortical surface).
If they are not given, <vol.nii.gz> will be used as the input volume for their steps.

The '--dilate' option will add a can to wb_commands -cifti-dilate function
(with the specified mm option) to expand clusters and fill holes.

If <subject> is set to 'HCP_S1200_GroupAvg' the volume with project to the surfaces
of the HCP S900 release Average subject.  This 'average fiducial mapping' approach
is not recommended in most cases, as group average surfaces do not encapsulate
all of the gray matter cortical ribbon.

(see https://github.com/edickie/ciftify/wiki/ciftify_vol_result-usage)

Written by Erin W Dickie, Mar 1, 2016
"""

import os
import sys
import subprocess
import logging
import logging.config

import numpy as np
from docopt import docopt

import ciftify
from ciftify.utils import run, WorkDirSettings

# Read logging.conf
config_path = os.path.join(os.path.dirname(__file__), "logging.conf")
logging.config.fileConfig(config_path, disable_existing_loggers=False)
logger = logging.getLogger(os.path.basename(__file__))


def run_ciftify_vol_result(settings, tmpdir):
    '''runs the magic '''

    ## project the surface data
    for hemi in ['L','R']:
        surf_mapping_cmd = ['wb_command', '-volume-to-surface-mapping',
            settings.surface_nii,
            os.path.join(settings.surf_dir,
                '{}.{}.midthickness{}.surf.gii'.format(
                    settings.subject, hemi, settings.surf_mesh)),
            os.path.join(tmpdir, '{}.func.gii'.format(hemi))]
        if settings.integer_labels:
            surf_mapping_cmd.append('-enclosing')
        else:
            surf_mapping_cmd.extend(['-ribbon-constrained',
                    os.path.join(settings.surf_dir,
                        '{}.{}.white{}.surf.gii'.format(
                            settings.subject,hemi,settings.surf_mesh)),
                    os.path.join(settings.surf_dir,
                        '{}.{}.pial{}.surf.gii'.format(
                            settings.subject,hemi,settings.surf_mesh))])
        run(surf_mapping_cmd)

    ## if asked to resample the volume...do this step
    if settings.resample:
        rinput_subcortical = os.path.join(tmpdir, 'input_nii_r.nii.gz')
        if settings.integer_labels:
            resample_method = 'ENCLOSING_VOXEL'
        else:
            resample_method = 'CUBIC'
        run(['wb_command', '-volume-affine-resample',
            settings.subcortical_nii,
            os.path.join(ciftify.config.find_fsl(),'etc', 'flirtsch/ident.mat'),
            settings.atlas_vol,
            resample_method,
            rinput_subcortical])

    else:  rinput_subcortical = settings.subcortical_nii

    if settings.dilate_mm:
        if settings.outputname.endswith('dtseries.nii'):
            dense_out = os.path.join(tmpdir,'dense1.dtseries.nii')
        else:
            dense_out = os.path.join(tmpdir,'dense1.dscalar.nii')
    else:
        dense_out = settings.outputname

    ## combind all three into a dscalar..
    if settings.outputname.endswith('dtseries.nii'):
        wb_subcommand = '-cifti-create-dense-timeseries'
    else:
        wb_subcommand = '-cifti-create-dense-scalar'

    run(['wb_command',wb_subcommand,
            dense_out,
            '-volume',rinput_subcortical, settings.atlas_vol,
            '-left-metric', os.path.join(tmpdir, 'L.func.gii'),
            '-roi-left', settings.surf_roi_L,
            '-right-metric', os.path.join(tmpdir, 'R.func.gii'),
            '-roi-right', settings.surf_roi_R])

    ## run the dilation is asked for..
    if settings.dilate_mm:
        dilate_cmd = ['wb_command', '-cifti-dilate',
            dense_out, 'COLUMN',
            str(settings.dilate_mm), str(settings.dilate_mm),
            settings.outputname,
            '-left-surface',
            os.path.join(settings.surf_dir,
                '{}.L.midthickness{}.surf.gii'.format(settings.subject, settings.surf_mesh)),
            '-right-surface',
            os.path.join(settings.surf_dir,
                '{}.R.midthickness{}.surf.gii'.format(settings.subject,settings.surf_mesh))]
        if settings.integer_labels:
            dilate_cmd.append('-nearest')
        run(dilate_cmd)

class UserSettings(WorkDirSettings):
    def __init__(self, arguments):
        WorkDirSettings.__init__(self, arguments)
        self.integer_labels = arguments['--integer-labels']
        self.resample = arguments['--resample-nifti']
        self.dilate_mm = arguments['--dilate']
        self.outputname = self.get_output_filename(arguments['<output.dscalar.nii>'])
        self.use_ciftify_global = self.use_ciftify_global(arguments['<subject>'])
        self.subject = self.get_subject(arguments['<subject>'])
        self.surf_dir = self.get_surf_dir()
        self.surf_mesh = self.get_surface_mesh(arguments['--HCP-MSMAll'])
        self.atlas_vol = self.get_atlas_vol()
        self.surf_roi_L = self.get_surf_roi('L')
        self.surf_roi_R = self.get_surf_roi('R')
        self.surface_nii = self.get_surface_nii(arguments)
        self.subcortical_nii = self.get_subcortical_nii(arguments)

    def get_output_filename(self, user_outputname):
        '''
        check that we have permissions to write to output directory
        adds 'dscalar.nii' to end of outputname if not already present
        '''
        outputname = os.path.realpath(user_outputname)
        output_dir = os.path.dirname(outputname)
        if not os.access(output_dir, os.W_OK):
            logger.error('Cannot write to output file {}\n'\
                         'The folder does not exist, or you do not have permission to write there'\
                         ''.format(outputname))
            sys.exit(1)
        if not outputname.endswith('dscalar.nii'):
            if not outputname.endswith('dtseries.nii'):
                logger.info("Appending '.dscalar.nii' extension to outputname")
                outputname = '{}.dscalar.nii'.format(outputname)
        return outputname

    def use_ciftify_global(self, hcp_subject):
        '''
        determine if the magical "global subject" ('HCP_S1200_GroupAvg') is in use
        '''
        if hcp_subject == 'HCP_S1200_GroupAvg':
            return True
        return False

    def get_subject(self, subject):
        ''' returns subject if '''
        if subject == 'HCP_S1200_GroupAvg':
            return 'S1200'
        return subject

    def get_surf_dir(self):
        ''' returns the directory containing the surface files '''
        if self.use_ciftify_global:
            surface_dir = ciftify.config.find_HCP_S1200_GroupAvg()
        else:
            surface_dir = os.path.join(self.work_dir,self.subject,
                'MNINonLinear','fsaverage_LR32k')
        return surface_dir

    def get_surface_mesh(self, use_MSMall):
        ''' returns a string needed to create the surface filesnames '''
        if self.use_ciftify_global:
            return '_MSMAll.32k_fs_LR'
        if use_MSMall:
            surface_mesh = '_MSMAll.32k_fs_LR'
        else:
            surface_mesh = '.32k_fs_LR'
        return surface_mesh

    def get_atlas_vol(self):
        ''' returns the subcortical atlas that is used during resampling '''
        if self.use_ciftify_global:
            atlas_vol = os.path.join(ciftify.config.find_ciftify_global(),
                '91282_Greyordinates','Atlas_ROIs.2.nii.gz')
        else:
            atlas_vol = os.path.join(self.work_dir, self.subject,
                'MNINonLinear','ROIs','Atlas_ROIs.2.nii.gz')
        if not os.path.exists(atlas_vol):
            logger.error('Subcortical atlas volume {} not found'.format(atlas_vol))
            sys.exit(1)
        return atlas_vol

    def get_surf_roi(self, hemi):
        ''' returns the path to the surface mask of the medial wall '''
        if self.use_ciftify_global:
            surf_roi = os.path.join(ciftify.config.find_ciftify_global(),
            '91282_Greyordinates','{}.atlasroi.32k_fs_LR.shape.gii'.format(hemi))
        else:
            surf_roi =  os.path.join(self.surf_dir,
                '{}.{}.atlasroi.32k_fs_LR.shape.gii'.format(self.subject,
                                                            hemi))
        if not os.path.exists(surf_roi):
            logger.error('Surface midline roi, {}, not found'.format(surf_roi))
            sys.exit(1)
        return surf_roi

    def get_surface_nii(self, arguments):
        ''' returns the volume to-be mapped to the surface '''
        surface_nii = arguments['--surface-vol']
        if not surface_nii:
            surface_nii = arguments['<vol.nii.gz>']
        if not os.path.isfile(surface_nii):
            logger.critical('Input {}. Does not exist'.format(surface_nii))
            sys.exit(1)
        if not surface_nii:
            logger.critical('No volume given for the surface projection')
            sys.exit(1)
        return surface_nii

    def get_subcortical_nii(self, arguments):
        ''' return the volume to resample the subcortical volumes from '''
        subcortical_nii = arguments['--subcortical-vol']
        if not subcortical_nii:
            subcortical_nii = arguments['<vol.nii.gz>']
        if not os.path.isfile(subcortical_nii):
            logger.critical('Input {}. Does not exist'.format(subcortical_nii))
            sys.exit(1)
        if not self.resample:
            atlas_spacing = ciftify.niio.voxel_spacing(self.atlas_vol)
            if ciftify.niio.voxel_spacing(subcortical_nii) != atlas_spacing:
                logger.error('Voxel sizes of input {} and atlas {} do not match.\n' \
                            'To explicitly resample the input, use the --resample-nifti flag' \
                            ''.format(subcortical_nii, self.atlas_vol))
                sys.exit(1)
        return subcortical_nii

def main():
    arguments       = docopt(__doc__)
    debug           = arguments['--debug']

    if debug:
        logger.setLevel(logging.DEBUG)
        logging.getLogger('ciftify').setLevel(logging.DEBUG)

    ## set up the top of the log
    logger.info('{}{}'.format(ciftify.utils.ciftify_logo(),
        ciftify.utils.section_header('Starting ciftify_vol_result')))
    ciftify.utils.log_arguments(arguments)

    settings = UserSettings(arguments)

    with ciftify.utils.TempDir() as tmpdir:
        logger.info('Creating tempdir:{} on host:{}'.format(tmpdir,
                    os.uname()[1]))
        ret = run_ciftify_vol_result(settings, tmpdir)

    logger.info(ciftify.utils.section_header('Done ciftify_vol_result'))
    sys.exit(ret)

if __name__ == '__main__':
    main()
