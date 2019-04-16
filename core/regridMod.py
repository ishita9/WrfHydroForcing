"""
Regridding module file for regridding input forcing files.
"""
import ESMF
import os
import sys
from core import errMod
import subprocess
from netCDF4 import Dataset
import numpy as np
from core import ioMod

def regrid_conus_hrrr(input_forcings,ConfigOptions,wrfHydroGeoMeta,MpiConfig):
    """
    Function for handling regridding of HRRR data.
    :param input_forcings:
    :param ConfigOptions:
    :param wrfHydroGeoMeta:
    :param MpiConfig:
    :return:
    """
    # Check to see if the regrid complete flag for this
    # output time step is true. This entails the necessary
    # inputs have already been regridded and we can move on.
    # print("REGRID STATUS = " + str(input_forcings.regridComplete))
    if input_forcings.regridComplete:
        return

    if MpiConfig.rank == 0:
        print("REGRID STATUS = " + str(input_forcings.regridComplete))
    # Create a path for a temporary NetCDF files that will
    # be created through the wgrib2 process.
    input_forcings.tmpFile = ConfigOptions.scratch_dir + "/" + \
        "HRRR_CONUS_TMP.nc"
    input_forcings.tmpFileHeight = ConfigOptions.scratch_dir + "/" + \
                                   "HRRR_CONUS_TMP_HEIGHT.nc"

    MpiConfig.comm.barrier()

    # This file shouldn't exist.... but if it does (previously failed
    # execution of the program), remove it.....
    if MpiConfig.rank == 0:
        if os.path.isfile(input_forcings.tmpFile):
            ConfigOptions.statusMsg = "Found old temporary file: " + \
                                      input_forcings.tmpFile + " - Removing....."
            errMod.log_warning(ConfigOptions)
            try:
                os.remove(input_forcings.tmpFile)
            except:
                errMod.err_out(ConfigOptions)

    MpiConfig.comm.barrier()

    forceCount = 0
    for forceTmp in input_forcings.grib_vars:
        # Create a temporary NetCDF file from the GRIB2 file.
        cmd = "wgrib2 " + input_forcings.file_in2 + " -match \":(" + \
              input_forcings.grib_vars[forceCount] + "):(" + \
              input_forcings.grib_levels[forceCount] + "):(" + str(input_forcings.fcst_hour2) + \
              " hour fcst):\" -netcdf " + input_forcings.tmpFile

        idTmp = ioMod.open_grib2(input_forcings.file_in2, input_forcings.tmpFile, cmd,
                                 ConfigOptions, MpiConfig, input_forcings.netcdf_var_names[forceCount])
        MpiConfig.comm.barrier()

        calcRegridFlag = check_regrid_status(idTmp, forceCount, input_forcings,
                                             ConfigOptions, MpiConfig, wrfHydroGeoMeta)

        if calcRegridFlag:
            if MpiConfig.rank == 0:
                print('CALCULATING WEIGHTS')
            calculate_weights(MpiConfig, ConfigOptions,
                              forceCount, input_forcings, idTmp)

            # Read in the HRRR height field, which is used for downscaling purposes.
            if MpiConfig.rank == 0:
                print("READING IN HRRR HEIGHT FIELD")
            cmd = "wgrib2 " + input_forcings.file_in2 + " -match " + \
                "\":(HGT):(surface):\" " + \
                " -netcdf " + input_forcings.tmpFileHeight
            idTmpHeight = ioMod.open_grib2(input_forcings.file_in2,input_forcings.tmpFileHeight,
                                           cmd,ConfigOptions,MpiConfig,'HGT_surface')
            MpiConfig.comm.barrier()

            # Regrid the height variable.
            if MpiConfig.rank == 0:
                varTmp = idTmpHeight.variables['HGT_surface'][0,:,:]
            else:
                varTmp = None
            MpiConfig.comm.barrier()

            varSubTmp = MpiConfig.scatter_array(input_forcings,varTmp,ConfigOptions)
            MpiConfig.comm.barrier()

            input_forcings.esmf_field_in.data[:,:] = varSubTmp
            MpiConfig.comm.barrier()

            if MpiConfig.rank == 0:
                print("REGRIDDING HRRR HEIGHT FIELD")
            input_forcings.esmf_field_out = input_forcings.regridObj(input_forcings.esmf_field_in,
                                                                     input_forcings.esmf_field_out)
            # Set any pixel cells outside the input domain to the global missing value.
            input_forcings.esmf_field_out.data[np.where(input_forcings.regridded_mask == 0)] = \
                ConfigOptions.globalNdv
            MpiConfig.comm.barrier()

            input_forcings.height[:,:] = input_forcings.esmf_field_out.data
            MpiConfig.comm.barrier()

            # Close the temporary NetCDF file and remove it.
            if MpiConfig.rank == 0:
                try:
                    idTmpHeight.close()
                except:
                    ConfigOptions.errMsg = "Unable to close temporary file: " + input_forcings.tmpFileHeight
                    raise Exception()

                try:
                    os.remove(input_forcings.tmpFileHeight)
                except:
                    ConfigOptions.errMsg = "Unable to remove temporary file: " + input_forcings.tmpFileHeight
                    raise Exception()

        MpiConfig.comm.barrier()

        # Regrid the input variables.
        if MpiConfig.rank == 0:
            print("REGRIDDING: " + input_forcings.netcdf_var_names[forceCount])
            varTmp = idTmp.variables[input_forcings.netcdf_var_names[forceCount]][0,:,:]
        else:
            varTmp = None
        MpiConfig.comm.barrier()

        varSubTmp = MpiConfig.scatter_array(input_forcings, varTmp, ConfigOptions)
        MpiConfig.comm.barrier()

        input_forcings.esmf_field_in.data[:,:] = varSubTmp
        MpiConfig.comm.barrier()

        input_forcings.esmf_field_out = input_forcings.regridObj(input_forcings.esmf_field_in,
                                                                 input_forcings.esmf_field_out)
        # Set any pixel cells outside the input domain to the global missing value.
        input_forcings.esmf_field_out.data[np.where(input_forcings.regridded_mask == 0)] = \
            ConfigOptions.globalNdv
        MpiConfig.comm.barrier

        input_forcings.regridded_forcings2[input_forcings.input_map_output[forceCount],:,:] = \
            input_forcings.esmf_field_out.data
        MpiConfig.comm.barrier()

        # If we are on the first timestep, set the previous regridded field to be
        # the latest as there are no states for time 0.
        if ConfigOptions.current_output_step == 1:
            input_forcings.regridded_forcings1[input_forcings.input_map_output[forceCount], :, :] = \
                input_forcings.regridded_forcings2[input_forcings.input_map_output[forceCount], :, :]
        MpiConfig.comm.barrier()

        # Close the temporary NetCDF file and remove it.
        if MpiConfig.rank == 0:
            try:
                idTmp.close()
            except:
                ConfigOptions.errMsg = "Unable to close NetCDF file: " + input_forcings.tmpFile
                errMod.err_out(ConfigOptions)
            try:
                os.remove(input_forcings.tmpFile)
            except:
                ConfigOptions.errMsg = "Unable to remove NetCDF file: " + input_forcings.tmpFile
                errMod.err_out()

        forceCount = forceCount + 1

def regrid_conus_rap(input_forcings,ConfigOptions,wrfHydroGeoMeta,MpiConfig):
    """
    Function for handling regridding of RAP 13km conus data.
    :param input_forcings:
    :param ConfigOptions:
    :param wrfHydroGeoMeta:
    :param MpiConfig:
    :return:
    """
    # Check to see if the regrid complete flag for this
    # output time step is true. This entails the necessary
    # inputs have already been regridded and we can move on.
    # print("REGRID STATUS = " + str(input_forcings.regridComplete))
    if input_forcings.regridComplete:
        return

    if MpiConfig.rank == 0:
        print("REGRID STATUS = " + str(input_forcings.regridComplete))
    # Create a path for a temporary NetCDF files that will
    # be created through the wgrib2 process.
    input_forcings.tmpFile = ConfigOptions.scratch_dir + "/" + \
        "RAP_CONUS_TMP.nc"
    input_forcings.tmpFileHeight = ConfigOptions.scratch_dir + "/" + \
                                   "RAP_CONUS_TMP_HEIGHT.nc"

    MpiConfig.comm.barrier()

    # This file shouldn't exist.... but if it does (previously failed
    # execution of the program), remove it.....
    if MpiConfig.rank == 0:
        if os.path.isfile(input_forcings.tmpFile):
            ConfigOptions.statusMsg = "Found old temporary file: " + \
                                      input_forcings.tmpFile + " - Removing....."
            errMod.log_warning(ConfigOptions)
            try:
                os.remove(input_forcings.tmpFile)
            except:
                errMod.err_out(ConfigOptions)

    MpiConfig.comm.barrier()

    forceCount = 0
    for forceTmp in input_forcings.grib_vars:
        # Create a temporary NetCDF file from the GRIB2 file.
        cmd = "wgrib2 " + input_forcings.file_in2 + " -match \":(" + \
              input_forcings.grib_vars[forceCount] + "):(" + \
              input_forcings.grib_levels[forceCount] + "):(" + str(input_forcings.fcst_hour2) + \
              " hour fcst):\" -netcdf " + input_forcings.tmpFile

        idTmp = ioMod.open_grib2(input_forcings.file_in2, input_forcings.tmpFile, cmd,
                                 ConfigOptions, MpiConfig, input_forcings.netcdf_var_names[forceCount])
        MpiConfig.comm.barrier()

        calcRegridFlag = check_regrid_status(idTmp, forceCount, input_forcings,
                                             ConfigOptions, MpiConfig, wrfHydroGeoMeta)

        if calcRegridFlag:
            if MpiConfig.rank == 0:
                print('CALCULATING WEIGHTS')
            calculate_weights(MpiConfig, ConfigOptions,
                              forceCount, input_forcings, idTmp)

            # Read in the RAP height field, which is used for downscaling purposes.
            if MpiConfig.rank == 0:
                print("READING IN RAP HEIGHT FIELD")
            cmd = "wgrib2 " + input_forcings.file_in2 + " -match " + \
                "\":(HGT):(surface):\" " + \
                " -netcdf " + input_forcings.tmpFileHeight
            idTmpHeight = ioMod.open_grib2(input_forcings.file_in2,input_forcings.tmpFileHeight,
                                           cmd,ConfigOptions,MpiConfig,'HGT_surface')
            MpiConfig.comm.barrier()

            # Regrid the height variable.
            if MpiConfig.rank == 0:
                varTmp = idTmpHeight.variables['HGT_surface'][0,:,:]
            else:
                varTmp = None
            MpiConfig.comm.barrier()

            varSubTmp = MpiConfig.scatter_array(input_forcings,varTmp,ConfigOptions)
            MpiConfig.comm.barrier()

            input_forcings.esmf_field_in.data[:,:] = varSubTmp
            MpiConfig.comm.barrier()

            if MpiConfig.rank == 0:
                print("REGRIDDING RAP HEIGHT FIELD")
            input_forcings.esmf_field_out = input_forcings.regridObj(input_forcings.esmf_field_in,
                                                                     input_forcings.esmf_field_out)
            # Set any pixel cells outside the input domain to the global missing value.
            input_forcings.esmf_field_out.data[np.where(input_forcings.regridded_mask == 0)] = \
                ConfigOptions.globalNdv
            MpiConfig.comm.barrier()

            input_forcings.height[:,:] = input_forcings.esmf_field_out.data
            MpiConfig.comm.barrier()

            # Close the temporary NetCDF file and remove it.
            if MpiConfig.rank == 0:
                try:
                    idTmpHeight.close()
                except:
                    ConfigOptions.errMsg = "Unable to close temporary file: " + input_forcings.tmpFileHeight
                    raise Exception()

                try:
                    os.remove(input_forcings.tmpFileHeight)
                except:
                    ConfigOptions.errMsg = "Unable to remove temporary file: " + input_forcings.tmpFileHeight
                    raise Exception()

        MpiConfig.comm.barrier()

        # Regrid the input variables.
        if MpiConfig.rank == 0:
            print("REGRIDDING: " + input_forcings.netcdf_var_names[forceCount])
            varTmp = idTmp.variables[input_forcings.netcdf_var_names[forceCount]][0,:,:]
        else:
            varTmp = None
        MpiConfig.comm.barrier()

        varSubTmp = MpiConfig.scatter_array(input_forcings, varTmp, ConfigOptions)
        MpiConfig.comm.barrier()

        input_forcings.esmf_field_in.data[:,:] = varSubTmp
        MpiConfig.comm.barrier()

        input_forcings.esmf_field_out = input_forcings.regridObj(input_forcings.esmf_field_in,
                                                                 input_forcings.esmf_field_out)
        # Set any pixel cells outside the input domain to the global missing value.
        input_forcings.esmf_field_out.data[np.where(input_forcings.regridded_mask == 0)] = \
            ConfigOptions.globalNdv
        MpiConfig.comm.barrier()

        input_forcings.regridded_forcings2[input_forcings.input_map_output[forceCount],:,:] = \
            input_forcings.esmf_field_out.data
        MpiConfig.comm.barrier()

        # If we are on the first timestep, set the previous regridded field to be
        # the latest as there are no states for time 0.
        if ConfigOptions.current_output_step == 1:
            input_forcings.regridded_forcings1[input_forcings.input_map_output[forceCount], :, :] = \
                input_forcings.regridded_forcings2[input_forcings.input_map_output[forceCount], :, :]
        MpiConfig.comm.barrier()

        # If we are on the first timestep, set the previous regridded field to be
        # the latest as there are no states for time 0.
        if ConfigOptions.current_output_step == 1:
            input_forcings.regridded_forcings1[input_forcings.input_map_output[forceCount], :, :] = \
                input_forcings.regridded_forcings2[input_forcings.input_map_output[forceCount], :, :]
        MpiConfig.comm.barrier()

        # Close the temporary NetCDF file and remove it.
        if MpiConfig.rank == 0:
            try:
                idTmp.close()
            except:
                ConfigOptions.errMsg = "Unable to close NetCDF file: " + input_forcings.tmpFile
                errMod.err_out(ConfigOptions)
            try:
                os.remove(input_forcings.tmpFile)
            except:
                ConfigOptions.errMsg = "Unable to remove NetCDF file: " + input_forcings.tmpFile
                errMod.err_out()

        forceCount = forceCount + 1

def regrid_cfsv2(input_forcings,ConfigOptions,wrfHydroGeoMeta,MpiConfig):
    """
    Function for handling regridding of global CFSv2 forecast data.
    :param input_forcings:
    :param ConfigOptions:
    :param wrfHydroGeoMeta:
    :param MpiConfig:
    :return:
    """
    # Check to see if the regrid complete flag for this
    # output time step is true. This entails the necessary
    # inputs have already been regridded and we can move on.
    # print("REGRID STATUS = " + str(input_forcings.regridComplete))
    if input_forcings.regridComplete:
        return

    if MpiConfig.rank == 0:
        print("REGRID STATUS = " + str(input_forcings.regridComplete))
    # Create a path for a temporary NetCDF files that will
    # be created through the wgrib2 process.
    input_forcings.tmpFile = ConfigOptions.scratch_dir + "/" + \
        "CFSv2_TMP.nc"
    input_forcings.tmpFileHeight = ConfigOptions.scratch_dir + "/" + \
                                   "CFSv2_TMP_HEIGHT.nc"

    MpiConfig.comm.barrier()

    # This file shouldn't exist.... but if it does (previously failed
    # execution of the program), remove it.....
    if MpiConfig.rank == 0:
        if os.path.isfile(input_forcings.tmpFile):
            ConfigOptions.statusMsg = "Found old temporary file: " + \
                                      input_forcings.tmpFile + " - Removing....."
            errMod.log_warning(ConfigOptions)
            try:
                os.remove(input_forcings.tmpFile)
            except:
                errMod.err_out(ConfigOptions)

    MpiConfig.comm.barrier()

    forceCount = 0
    for forceTmp in input_forcings.grib_vars:
        # Create a temporary NetCDF file from the GRIB2 file.
        cmd = "wgrib2 " + input_forcings.file_in2 + " -match \":(" + \
              input_forcings.grib_vars[forceCount] + "):(" + \
              input_forcings.grib_levels[forceCount] + "):(" + str(input_forcings.fcst_hour2) + \
              " hour fcst):\" -netcdf " + input_forcings.tmpFile

        idTmp = ioMod.open_grib2(input_forcings.file_in2, input_forcings.tmpFile, cmd,
                                 ConfigOptions, MpiConfig, input_forcings.netcdf_var_names[forceCount])
        MpiConfig.comm.barrier()

        calcRegridFlag = check_regrid_status(idTmp, forceCount, input_forcings,
                                             ConfigOptions, MpiConfig, wrfHydroGeoMeta)

        if calcRegridFlag:
            if MpiConfig.rank == 0:
                print('CALCULATING WEIGHTS')
            calculate_weights(MpiConfig, ConfigOptions,
                              forceCount, input_forcings, idTmp)

            # Read in the RAP height field, which is used for downscaling purposes.
            if MpiConfig.rank == 0:
                print("READING IN CFSv2 HEIGHT FIELD")
            cmd = "wgrib2 " + input_forcings.file_in2 + " -match " + \
                "\":(HGT):(surface):\" " + \
                " -netcdf " + input_forcings.tmpFileHeight
            idTmpHeight = ioMod.open_grib2(input_forcings.file_in2,input_forcings.tmpFileHeight,
                                           cmd,ConfigOptions,MpiConfig,'HGT_surface')
            MpiConfig.comm.barrier()

            # Regrid the height variable.
            if MpiConfig.rank == 0:
                varTmp = idTmpHeight.variables['HGT_surface'][0,:,:]
            else:
                varTmp = None
            MpiConfig.comm.barrier()

            varSubTmp = MpiConfig.scatter_array(input_forcings,varTmp,ConfigOptions)
            MpiConfig.comm.barrier()

            input_forcings.esmf_field_in.data[:,:] = varSubTmp
            MpiConfig.comm.barrier()

            if MpiConfig.rank == 0:
                print("REGRIDDING CFSv2 HEIGHT FIELD")
            input_forcings.esmf_field_out = input_forcings.regridObj(input_forcings.esmf_field_in,
                                                                     input_forcings.esmf_field_out)
            # Set any pixel cells outside the input domain to the global missing value.
            input_forcings.esmf_field_out.data[np.where(input_forcings.regridded_mask == 0)] = \
                ConfigOptions.globalNdv
            MpiConfig.comm.barrier()

            input_forcings.height[:,:] = input_forcings.esmf_field_out.data
            MpiConfig.comm.barrier()

            # Close the temporary NetCDF file and remove it.
            if MpiConfig.rank == 0:
                try:
                    idTmpHeight.close()
                except:
                    ConfigOptions.errMsg = "Unable to close temporary file: " + input_forcings.tmpFileHeight
                    raise Exception()

                try:
                    os.remove(input_forcings.tmpFileHeight)
                except:
                    ConfigOptions.errMsg = "Unable to remove temporary file: " + input_forcings.tmpFileHeight
                    raise Exception()

        MpiConfig.comm.barrier()

        # Regrid the input variables.
        if MpiConfig.rank == 0:
            print("REGRIDDING: " + input_forcings.netcdf_var_names[forceCount])
            varTmp = idTmp.variables[input_forcings.netcdf_var_names[forceCount]][0,:,:]
        else:
            varTmp = None
        MpiConfig.comm.barrier()

        varSubTmp = MpiConfig.scatter_array(input_forcings, varTmp, ConfigOptions)
        MpiConfig.comm.barrier()

        input_forcings.esmf_field_in.data[:,:] = varSubTmp
        MpiConfig.comm.barrier()

        input_forcings.esmf_field_out = input_forcings.regridObj(input_forcings.esmf_field_in,
                                                                 input_forcings.esmf_field_out)
        # Set any pixel cells outside the input domain to the global missing value.
        input_forcings.esmf_field_out.data[np.where(input_forcings.regridded_mask == 0)] = \
            ConfigOptions.globalNdv
        MpiConfig.comm.barrier()

        input_forcings.regridded_forcings2[input_forcings.input_map_output[forceCount],:,:] = \
            input_forcings.esmf_field_out.data
        MpiConfig.comm.barrier()

        # If we are on the first timestep, set the previous regridded field to be
        # the latest as there are no states for time 0.
        if ConfigOptions.current_output_step == 1:
            input_forcings.regridded_forcings1[input_forcings.input_map_output[forceCount], :, :] = \
                input_forcings.regridded_forcings2[input_forcings.input_map_output[forceCount], :, :]
        MpiConfig.comm.barrier()

        # Close the temporary NetCDF file and remove it.
        if MpiConfig.rank == 0:
            try:
                idTmp.close()
            except:
                ConfigOptions.errMsg = "Unable to close NetCDF file: " + input_forcings.tmpFile
                errMod.err_out(ConfigOptions)
            try:
                os.remove(input_forcings.tmpFile)
            except:
                ConfigOptions.errMsg = "Unable to remove NetCDF file: " + input_forcings.tmpFile
                errMod.err_out()

        forceCount = forceCount + 1

def regrid_custom_hourly_netcdf(input_forcings,ConfigOptions,wrfHydroGeoMeta,MpiConfig):
    """
    Function for handling regridding of custom input NetCDF hourly forcing files.
    :param input_forcings:
    :param ConfigOptions:
    :param wrfHydroGeoMeta:
    :param MpiConfig:
    :return:
    """
    # Check to see if the regrid complete flag for this
    # output time step is true. This entails the necessary
    # inputs have already been regridded and we can move on.
    # print("REGRID STATUS = " + str(input_forcings.regridComplete))
    if input_forcings.regridComplete:
        return

    if MpiConfig.rank == 0:
        print("REGRID STATUS = " + str(input_forcings.regridComplete))
    MpiConfig.comm.barrier()

    # Open the input NetCDF file containing necessary data.
    idTmp = ioMod.open_netcdf_forcing(input_forcings.file_in2,ConfigOptions,MpiConfig)
    MpiConfig.comm.barrier()

    forceCount = 0
    for forceTmp in input_forcings.netcdf_var_names:
        calcRegridFlag = check_regrid_status(idTmp, forceCount, input_forcings,
                                             ConfigOptions, MpiConfig, wrfHydroGeoMeta)

        if calcRegridFlag:
            if MpiConfig.rank == 0:
                print('CALCULATING WEIGHTS')
            calculate_weights(MpiConfig, ConfigOptions,
                              forceCount, input_forcings, idTmp)

            # Read in the RAP height field, which is used for downscaling purposes.
            if MpiConfig.rank == 0:
                print("READING IN CUSTOM HEIGHT FIELD")
            if 'HGT_surface' not in idTmp.variables.keys():
                ConfigOptions.errMsg = "Unable to locate HGT_surface in: " + input_forcings.file_in2
                raise Exception()
            MpiConfig.comm.barrier()

            # Regrid the height variable.
            if MpiConfig.rank == 0:
                varTmp = idTmp.variables['HGT_surface'][0,:,:]
            else:
                varTmp = None
            MpiConfig.comm.barrier()

            varSubTmp = MpiConfig.scatter_array(input_forcings,varTmp,ConfigOptions)
            MpiConfig.comm.barrier()

            input_forcings.esmf_field_in.data[:,:] = varSubTmp
            MpiConfig.comm.barrier()

            if MpiConfig.rank == 0:
                print("REGRIDDING CUSTOM HEIGHT FIELD")
            input_forcings.esmf_field_out = input_forcings.regridObj(input_forcings.esmf_field_in,
                                                                     input_forcings.esmf_field_out)
            # Set any pixel cells outside the input domain to the global missing value.
            input_forcings.esmf_field_out.data[np.where(input_forcings.regridded_mask == 0)] = \
                ConfigOptions.globalNdv
            MpiConfig.comm.barrier()

            input_forcings.height[:,:] = input_forcings.esmf_field_out.data
            MpiConfig.comm.barrier()

        MpiConfig.comm.barrier()

        # Regrid the input variables.
        if MpiConfig.rank == 0:
            print("REGRIDDING: " + input_forcings.netcdf_var_names[forceCount])
            varTmp = idTmp.variables[input_forcings.netcdf_var_names[forceCount]][0,:,:]
        else:
            varTmp = None
        MpiConfig.comm.barrier()

        varSubTmp = MpiConfig.scatter_array(input_forcings, varTmp, ConfigOptions)
        MpiConfig.comm.barrier()

        input_forcings.esmf_field_in.data[:,:] = varSubTmp
        MpiConfig.comm.barrier()

        input_forcings.esmf_field_out = input_forcings.regridObj(input_forcings.esmf_field_in,
                                                                 input_forcings.esmf_field_out)
        # Set any pixel cells outside the input domain to the global missing value.
        input_forcings.esmf_field_out.data[np.where(input_forcings.regridded_mask == 0)] = \
            ConfigOptions.globalNdv
        MpiConfig.comm.barrier()

        input_forcings.regridded_forcings2[input_forcings.input_map_output[forceCount],:,:] = \
            input_forcings.esmf_field_out.data
        MpiConfig.comm.barrier()

        # If we are on the first timestep, set the previous regridded field to be
        # the latest as there are no states for time 0.
        if ConfigOptions.current_output_step == 1:
            input_forcings.regridded_forcings1[input_forcings.input_map_output[forceCount], :, :] = \
                input_forcings.regridded_forcings2[input_forcings.input_map_output[forceCount], :, :]
        MpiConfig.comm.barrier()

        # Close the temporary NetCDF file and remove it.
        if MpiConfig.rank == 0:
            try:
                idTmp.close()
            except:
                ConfigOptions.errMsg = "Unable to close NetCDF file: " + input_forcings.tmpFile
                errMod.err_out(ConfigOptions)
            try:
                os.remove(input_forcings.tmpFile)
            except:
                ConfigOptions.errMsg = "Unable to remove NetCDF file: " + input_forcings.tmpFile
                errMod.err_out()

        forceCount = forceCount + 1

def regrid_gfs(input_forcings,ConfigOptions,wrfHydroGeoMeta,MpiConfig):
    """
    Function for handing regridding of input GFS data
    fro GRIB2 files.
    :param input_forcings:
    :param ConfigOptions:
    :return:
    """
    # Check to see if the regrid complete flag for this
    # output time step is true. This entails the necessary
    # inputs have already been regridded and we can move on.
    if input_forcings.regridComplete:
        return

    if MpiConfig.rank == 0:
        print("REGRID STATUS = " + str(input_forcings.regridComplete))
    # Create a path for a temporary NetCDF files that will
    # be created through the wgrib2 process.
    input_forcings.tmpFile = ConfigOptions.scratch_dir + "/" + \
        "GFS_TMP.nc"
    input_forcings.tmpFileHeight = ConfigOptions.scratch_dir + "/" + \
                                   "GFS_TMP_HEIGHT.nc"

    MpiConfig.comm.barrier()

    # This file shouldn't exist.... but if it does (previously failed
    # execution of the program), remove it.....
    if MpiConfig.rank == 0:
        if os.path.isfile(input_forcings.tmpFile):
            ConfigOptions.statusMsg = "Found old temporary file: " + \
                input_forcings.tmpFile + " - Removing....."
            errMod.log_warning(ConfigOptions)
            try:
                os.remove(input_forcings.tmpFile)
            except:
                errMod.err_out(ConfigOptions)

    # We will process each variable at a time. Unfortunately, wgrib2 makes it a bit
    # difficult to handle forecast strings, otherwise this could be done in one commmand.
    # This makes a compelling case for the use of a GRIB Python API in the future....
    # Incoming shortwave radiation flux.....

    MpiConfig.comm.barrier()

    # Loop through all of the input forcings in GFS data. Convert the GRIB2 files
    # to NetCDF, read in the data, regrid it, then map it to the apropriate
    # array slice in the output arrays.
    forceCount = 0
    for forceTmp in input_forcings.grib_vars:
        # Create a temporary NetCDF file from the GRIB2 file.
        if forceTmp == "PRATE":
            # By far the most complicated of output variables. We need to calculate
            # our 'average' PRATE based on our current hour.
            if input_forcings.fcst_hour2 <= 240:
                tmpHrCurrent = input_forcings.fcst_hour2
                diffTmp = tmpHrCurrent%6
                if diffTmp == 0:
                    tmpHrPrevious = tmpHrCurrent - 6
                else:
                    tmpHrPrevious = tmpHrCurrent - diffTmp
            else:
                tmpHrPrevious = input_forcings.fcst_hour1

            cmd = "wgrib2 " + input_forcings.file_in2 + " -match \":(" + \
                  input_forcings.grib_vars[forceCount] + "):(" + \
                  input_forcings.grib_levels[forceCount] + "):(" + str(tmpHrPrevious) + \
                  "-" + str(input_forcings.fcst_hour2) + \
                  " hour ave fcst):\" -netcdf " + input_forcings.tmpFile
        else:
            cmd = "wgrib2 " + input_forcings.file_in2 + " -match \":(" + \
                  input_forcings.grib_vars[forceCount] + "):(" + \
                  input_forcings.grib_levels[forceCount] + "):(" + str(input_forcings.fcst_hour2) + \
                  " hour fcst):\" -netcdf " + input_forcings.tmpFile

        idTmp = ioMod.open_grib2(input_forcings.file_in2,input_forcings.tmpFile,cmd,
                                 ConfigOptions,MpiConfig,input_forcings.netcdf_var_names[forceCount])
        MpiConfig.comm.barrier()

        calcRegridFlag = check_regrid_status(idTmp,forceCount,input_forcings,
                                             ConfigOptions,MpiConfig,wrfHydroGeoMeta)

        if calcRegridFlag:
            if MpiConfig.rank == 0:
                print('CALCULATING WEIGHTS')
            calculate_weights(MpiConfig, ConfigOptions,
                              forceCount, input_forcings, idTmp)

            # Read in the GFS height field, which is used for downscaling purposes.
            if MpiConfig.rank == 0:
                print("READING IN GFS HEIGHT FIELD")
            cmd = "wgrib2 " + input_forcings.file_in2 + " -match " + \
                "\":(HGT):(surface):\" " + \
                " -netcdf " + input_forcings.tmpFileHeight
            idTmpHeight = ioMod.open_grib2(input_forcings.file_in2,input_forcings.tmpFileHeight,
                                           cmd,ConfigOptions,MpiConfig,'HGT_surface')
            MpiConfig.comm.barrier()

            # Regrid the height variable.
            if MpiConfig.rank == 0:
                varTmp = idTmpHeight.variables['HGT_surface'][0,:,:]
            else:
                varTmp = None
            MpiConfig.comm.barrier()

            varSubTmp = MpiConfig.scatter_array(input_forcings,varTmp,ConfigOptions)
            MpiConfig.comm.barrier()

            input_forcings.esmf_field_in.data[:,:] = varSubTmp
            MpiConfig.comm.barrier()

            if MpiConfig.rank == 0:
                print("REGRIDDING GFS HEIGHT FIELD")
            input_forcings.esmf_field_out = input_forcings.regridObj(input_forcings.esmf_field_in,
                                                                     input_forcings.esmf_field_out)
            # Set any pixel cells outside the input domain to the global missing value.
            input_forcings.esmf_field_out.data[np.where(input_forcings.regridded_mask == 0)] = \
                ConfigOptions.globalNdv
            MpiConfig.comm.barrier()

            input_forcings.height[:,:] = input_forcings.esmf_field_out.data
            MpiConfig.comm.barrier()

            # Close the temporary NetCDF file and remove it.
            if MpiConfig.rank == 0:
                try:
                    idTmpHeight.close()
                except:
                    ConfigOptions.errMsg = "Unable to close temporary file: " + input_forcings.tmpFileHeight
                    raise Exception()

                try:
                    os.remove(input_forcings.tmpFileHeight)
                except:
                    ConfigOptions.errMsg = "Unable to remove temporary file: " + input_forcings.tmpFileHeight
                    raise Exception()

        MpiConfig.comm.barrier()

        # Regrid the input variables.
        if MpiConfig.rank == 0:
            print("REGRIDDING: " + input_forcings.netcdf_var_names[forceCount])
            varTmp = idTmp.variables[input_forcings.netcdf_var_names[forceCount]][0,:,:]
        else:
            varTmp = None
        MpiConfig.comm.barrier()

        varSubTmp = MpiConfig.scatter_array(input_forcings, varTmp, ConfigOptions)
        MpiConfig.comm.barrier()

        input_forcings.esmf_field_in.data[:,:] = varSubTmp
        MpiConfig.comm.barrier()

        input_forcings.esmf_field_out = input_forcings.regridObj(input_forcings.esmf_field_in,
                                                                 input_forcings.esmf_field_out)
        # Set any pixel cells outside the input domain to the global missing value.
        input_forcings.esmf_field_out.data[np.where(input_forcings.regridded_mask == 0)] = \
            ConfigOptions.globalNdv
        MpiConfig.comm.barrier()

        input_forcings.regridded_forcings2[input_forcings.input_map_output[forceCount],:,:] = \
            input_forcings.esmf_field_out.data
        MpiConfig.comm.barrier()

        # If we are on the first timestep, set the previous regridded field to be
        # the latest as there are no states for time 0.
        if ConfigOptions.current_output_step == 1:
            input_forcings.regridded_forcings1[input_forcings.input_map_output[forceCount], :, :] = \
                input_forcings.regridded_forcings2[input_forcings.input_map_output[forceCount], :, :]
        MpiConfig.comm.barrier()

        # Close the temporary NetCDF file and remove it.
        if MpiConfig.rank == 0:
            try:
                idTmp.close()
            except:
                ConfigOptions.errMsg = "Unable to close NetCDF file: " + input_forcings.tmpFile
                errMod.err_out(ConfigOptions)
            try:
                os.remove(input_forcings.tmpFile)
            except:
                ConfigOptions.errMsg = "Unable to remove NetCDF file: " + input_forcings.tmpFile
                errMod.err_out()

        forceCount = forceCount + 1

def regrid_nam_nest(input_forcings,ConfigOptions,wrfHydroGeoMeta,MpiConfig):
    """
    Function for handing regridding of input NAM nest data
    fro GRIB2 files.
    :param input_forcings:
    :param ConfigOptions:
    :return:
    """
    # Check to see if the regrid complete flag for this
    # output time step is true. This entails the necessary
    # inputs have already been regridded and we can move on.
    if input_forcings.regridComplete:
        return

    if MpiConfig.rank == 0:
        print("REGRID STATUS = " + str(input_forcings.regridComplete))
    # Create a path for a temporary NetCDF files that will
    # be created through the wgrib2 process.
    input_forcings.tmpFile = ConfigOptions.scratch_dir + "/" + \
        "NAM_NEST_TMP.nc"
    input_forcings.tmpFileHeight = ConfigOptions.scratch_dir + "/" + \
                                   "NAM_NEST_TMP_HEIGHT.nc"

    MpiConfig.comm.barrier()

    # This file shouldn't exist.... but if it does (previously failed
    # execution of the program), remove it.....
    if MpiConfig.rank == 0:
        if os.path.isfile(input_forcings.tmpFile):
            ConfigOptions.statusMsg = "Found old temporary file: " + \
                input_forcings.tmpFile + " - Removing....."
            errMod.log_warning(ConfigOptions)
            try:
                os.remove(input_forcings.tmpFile)
            except:
                errMod.err_out(ConfigOptions)

    MpiConfig.comm.barrier()

    # Loop through all of the input forcings in NAM nest data. Convert the GRIB2 files
    # to NetCDF, read in the data, regrid it, then map it to the apropriate
    # array slice in the output arrays.
    forceCount = 0
    for forceTmp in input_forcings.grib_vars:
        # Create a temporary NetCDF file from the GRIB2 file.
        cmd = "wgrib2 " + input_forcings.file_in2 + " -match \":(" + \
              input_forcings.grib_vars[forceCount] + "):(" + \
              input_forcings.grib_levels[forceCount] + "):(" + str(input_forcings.fcst_hour2) + \
              " hour fcst):\" -netcdf " + input_forcings.tmpFile

        idTmp = ioMod.open_grib2(input_forcings.file_in2, input_forcings.tmpFile, cmd,
                                 ConfigOptions, MpiConfig, input_forcings.netcdf_var_names[forceCount])
        MpiConfig.comm.barrier()

        calcRegridFlag = check_regrid_status(idTmp, forceCount, input_forcings,
                                             ConfigOptions, MpiConfig, wrfHydroGeoMeta)

        if calcRegridFlag:
            if MpiConfig.rank == 0:
                print('CALCULATING WEIGHTS')
            calculate_weights(MpiConfig, ConfigOptions,
                              forceCount, input_forcings, idTmp)

            # Read in the RAP height field, which is used for downscaling purposes.
            if MpiConfig.rank == 0:
                print("READING IN NAM Nest HEIGHT FIELD")
            cmd = "wgrib2 " + input_forcings.file_in2 + " -match " + \
                  "\":(HGT):(surface):\" " + \
                  " -netcdf " + input_forcings.tmpFileHeight
            idTmpHeight = ioMod.open_grib2(input_forcings.file_in2, input_forcings.tmpFileHeight,
                                           cmd, ConfigOptions, MpiConfig, 'HGT_surface')
            MpiConfig.comm.barrier()

            # Regrid the height variable.
            if MpiConfig.rank == 0:
                varTmp = idTmpHeight.variables['HGT_surface'][0, :, :]
            else:
                varTmp = None
            MpiConfig.comm.barrier()

            varSubTmp = MpiConfig.scatter_array(input_forcings, varTmp, ConfigOptions)
            MpiConfig.comm.barrier()

            input_forcings.esmf_field_in.data[:, :] = varSubTmp
            MpiConfig.comm.barrier()

            if MpiConfig.rank == 0:
                print("REGRIDDING NAM Nest HEIGHT FIELD")
            input_forcings.esmf_field_out = input_forcings.regridObj(input_forcings.esmf_field_in,
                                                                     input_forcings.esmf_field_out)
            # Set any pixel cells outside the input domain to the global missing value.
            input_forcings.esmf_field_out.data[np.where(input_forcings.regridded_mask == 0)] = \
                ConfigOptions.globalNdv
            MpiConfig.comm.barrier()

            input_forcings.height[:, :] = input_forcings.esmf_field_out.data
            MpiConfig.comm.barrier()

            # Close the temporary NetCDF file and remove it.
            if MpiConfig.rank == 0:
                try:
                    idTmpHeight.close()
                except:
                    ConfigOptions.errMsg = "Unable to close temporary file: " + input_forcings.tmpFileHeight
                    raise Exception()

                try:
                    os.remove(input_forcings.tmpFileHeight)
                except:
                    ConfigOptions.errMsg = "Unable to remove temporary file: " + input_forcings.tmpFileHeight
                    raise Exception()

        MpiConfig.comm.barrier()

        # Regrid the input variables.
        if MpiConfig.rank == 0:
            print("REGRIDDING: " + input_forcings.netcdf_var_names[forceCount])
            varTmp = idTmp.variables[input_forcings.netcdf_var_names[forceCount]][0, :, :]
        else:
            varTmp = None
        MpiConfig.comm.barrier()

        varSubTmp = MpiConfig.scatter_array(input_forcings, varTmp, ConfigOptions)
        MpiConfig.comm.barrier()

        input_forcings.esmf_field_in.data[:, :] = varSubTmp
        MpiConfig.comm.barrier()

        input_forcings.esmf_field_out = input_forcings.regridObj(input_forcings.esmf_field_in,
                                                                 input_forcings.esmf_field_out)
        # Set any pixel cells outside the input domain to the global missing value.
        input_forcings.esmf_field_out.data[np.where(input_forcings.regridded_mask == 0)] = \
            ConfigOptions.globalNdv
        MpiConfig.comm.barrier()

        input_forcings.regridded_forcings2[input_forcings.input_map_output[forceCount], :, :] = \
            input_forcings.esmf_field_out.data
        MpiConfig.comm.barrier()

        # If we are on the first timestep, set the previous regridded field to be
        # the latest as there are no states for time 0.
        if ConfigOptions.current_output_step == 1:
            input_forcings.regridded_forcings1[input_forcings.input_map_output[forceCount], :, :] = \
                input_forcings.regridded_forcings2[input_forcings.input_map_output[forceCount], :, :]
        MpiConfig.comm.barrier()

        # Close the temporary NetCDF file and remove it.
        if MpiConfig.rank == 0:
            try:
                idTmp.close()
            except:
                ConfigOptions.errMsg = "Unable to close NetCDF file: " + input_forcings.tmpFile
                errMod.err_out(ConfigOptions)
            try:
                os.remove(input_forcings.tmpFile)
            except:
                ConfigOptions.errMsg = "Unable to remove NetCDF file: " + input_forcings.tmpFile
                errMod.err_out()

        forceCount = forceCount + 1

def regrid_mrms_hourly(supplemental_precip,ConfigOptions,wrfHydroGeoMeta,MpiConfig):
    """
    Function for handling regridding hourly MRMS precipitation. An RQI mask file
    Is necessary to filter out poor precipitation estimates.
    :param supplemental_precip:
    :param ConfigOptions:
    :param wrfHydroGeoMeta:
    :param MpiConfig:
    :return:
    """
    # Check to see if the regrid complete flag for this
    # output time step is true. This entails the necessary
    # inputs have already been regridded and we can move on.
    if supplemental_precip.regridComplete:
        return

    if MpiConfig.rank == 0:
        print("REGRID STATUS = " + str(supplemental_precip.regridComplete))
    # MRMS data originally is stored as .gz files. We need to compose a series
    # of temporary paths.
    # 1.) The unzipped GRIB2 precipitation file.
    # 2.) The unzipped GRIB2 RQI file.
    # 3.) A temporary NetCDF file that stores the precipitation grid.
    # 4.) A temporary NetCDF file that stores the RQI grid.
    # Create a path for a temporary NetCDF files that will
    # be created through the wgrib2 process.
    mrms_tmp_grib2 = ConfigOptions.scratch_dir + "/MRMS_PCP_TMP.grib2"
    mrms_tmp_nc = ConfigOptions.scratch_dir + "/MRMS_PCP_TMP.nc"
    mrms_tmp_rqi_grib2 = ConfigOptions.scratch_dir + "/MRMS_RQI_TMP.grib2"
    mrms_tmp_rqi_nc = ConfigOptions.scratch_dir + "/MRMS_RQI_TMP.nc"
    MpiConfig.comm.barrier()

    # If the input paths have been set to None, this means input is missing. We will
    # alert the user, and set the final output grids to be the global NDV and return.
    if not supplemental_precip.file_in1 or not supplemental_precip.file_in2:
        if MpiConfig.rank == 0:
            "NO MRMS PRECIP AVAILABLE. SETTING FINAL SUPP GRIDS TO NDV"
        supplemental_precip.regridded_precip2 = None
        supplemental_precip.regridded_precip1 = None
        return

    # These files shouldn't exist. If they do, remove them.
    if MpiConfig.rank == 0:
        if os.path.isfile(mrms_tmp_grib2):
            ConfigOptions.statusMsg = "Found old temporary file: " + \
                                      mrms_tmp_grib2 + " - Removing....."
            errMod.log_warning(ConfigOptions)
            try:
                os.remove(mrms_tmp_grib2)
            except:
                errMod.err_out(ConfigOptions)
        if os.path.isfile(mrms_tmp_nc):
            ConfigOptions.statusMsg = "Found old temporary file: " + \
                                      mrms_tmp_nc + " - Removing....."
            errMod.log_warning(ConfigOptions)
            try:
                os.remove(mrms_tmp_nc)
            except:
                errMod.err_out(ConfigOptions)
        if os.path.isfile(mrms_tmp_rqi_grib2):
            ConfigOptions.statusMsg = "Found old temporary file: " + \
                                      mrms_tmp_rqi_grib2 + " - Removing....."
            errMod.log_warning(ConfigOptions)
            try:
                os.remove(mrms_tmp_rqi_grib2)
            except:
                errMod.err_out(ConfigOptions)
        if os.path.isfile(mrms_tmp_rqi_nc):
            ConfigOptions.statusMsg = "Found old temporary file: " + \
                                      mrms_tmp_rqi_nc + " - Removing....."
            errMod.log_warning(ConfigOptions)
            try:
                os.remove(mrms_tmp_rqi_nc)
            except:
                errMod.err_out(ConfigOptions)

    MpiConfig.comm.barrier()

    # If the input paths have been set to None, this means input is missing. We will
    # alert the user, and set the final output grids to be the global NDV and return.
    if not supplemental_precip.file_in1 or not supplemental_precip.file_in2:
        if MpiConfig.rank == 0:
            "NO MRMS PRECIP AVAILABLE. SETTING FINAL SUPP GRIDS TO NDV"
        supplemental_precip.regridded_precip2 = None
        supplemental_precip.regridded_precip1 = None
        return

    # Unzip MRMS files to temporary locations.
    try:
        ioMod.unzip_file(supplemental_precip.file_in2,mrms_tmp_grib2,
                         ConfigOptions,MpiConfig)
    except:
        errMod.err_out(ConfigOptions)
    try:
        ioMod.unzip_file(supplemental_precip.rqi_file_in2,mrms_tmp_rqi_grib2,
                         ConfigOptions,MpiConfig)
    except:
        errMod.err_out(ConfigOptions)

    MpiConfig.comm.barrier()

    # Perform a GRIB dump to NetCDF for the MRMS precip and RQI data.
    cmd1 = "wgrib2 " + mrms_tmp_grib2 + " -netcdf " + mrms_tmp_nc
    idMrms = ioMod.open_grib2(mrms_tmp_grib2,mrms_tmp_nc,cmd1,ConfigOptions,
                              MpiConfig,supplemental_precip.netcdf_var_names[0])
    MpiConfig.comm.barrier()

    cmd2 = "wgrib2 " + mrms_tmp_rqi_grib2 + " -netcdf " + mrms_tmp_rqi_nc
    idMrmsRqi = ioMod.open_grib2(mrms_tmp_rqi_grib2, mrms_tmp_rqi_nc, cmd2, ConfigOptions,
                                 MpiConfig, supplemental_precip.rqi_netcdf_var_names[0])
    MpiConfig.comm.barrier()

    # Remove temporary GRIB2 files
    if MpiConfig.rank == 0:
        try:
            os.remove(mrms_tmp_grib2)
        except:
            ConfigOptions.errMsg = "Unable to remove GRIB2 file: " + mrms_tmp_grib2
            errMod.err_out()
        try:
            os.remove(mrms_tmp_rqi_grib2)
        except:
            ConfigOptions.errMsg = "Unable to remove GRIB2 file: " + mrms_tmp_rqi_grib2
            errMod.err_out()
    MpiConfig.comm.barrier()

    # Check to see if we need to calculate regridding weights.
    calcRegridFlag = check_supp_pcp_regrid_status(idMrms, supplemental_precip,ConfigOptions,
                                                  MpiConfig, wrfHydroGeoMeta)
    MpiConfig.comm.barrier()

    if calcRegridFlag:
        if MpiConfig.rank == 0:
            print('CALCULATING MRMS WEIGHTS')
        calculate_supp_pcp_weights(MpiConfig, ConfigOptions,
                                   supplemental_precip, idMrms,mrms_tmp_nc)

    # Regrid the RQI grid.
    if MpiConfig.rank == 0:
        varTmp = idMrmsRqi.variables[supplemental_precip.rqi_netcdf_var_names[0]][0, :, :]
    else:
        varTmp = None
    MpiConfig.comm.barrier()

    varSubTmp = MpiConfig.scatter_array(supplemental_precip, varTmp, ConfigOptions)
    MpiConfig.comm.barrier()

    supplemental_precip.esmf_field_in.data[:, :] = varSubTmp
    MpiConfig.comm.barrier()

    if MpiConfig.rank == 0:
        print("REGRIDDING MRMS RQI FIELD")
    supplemental_precip.esmf_field_out = supplemental_precip.regridObj(supplemental_precip.esmf_field_in,
                                                                       supplemental_precip.esmf_field_out)
    # Set any pixel cells outside the input domain to the global missing value.
    supplemental_precip.esmf_field_out.data[np.where(supplemental_precip.regridded_mask == 0)] = \
        ConfigOptions.globalNdv
    MpiConfig.comm.barrier()

    supplemental_precip.regridded_rqi2[:, :] = supplemental_precip.esmf_field_out.data
    MpiConfig.comm.barrier()

    # Close the temporary NetCDF file and remove it.
    if MpiConfig.rank == 0:
        try:
            idMrmsRqi.close()
        except:
            ConfigOptions.errMsg = "Unable to close NetCDF file: " + mrms_tmp_rqi_nc
            errMod.err_out(ConfigOptions)
        try:
            os.remove(mrms_tmp_rqi_nc)
        except:
            ConfigOptions.errMsg = "Unable to remove NetCDF file: " + mrms_tmp_rqi_nc
            errMod.err_out()

    MpiConfig.comm.barrier()

    # Regrid the input variables.
    if MpiConfig.rank == 0:
        print("REGRIDDING: " + supplemental_precip.netcdf_var_names[0])
        varTmp = idMrms.variables[supplemental_precip.netcdf_var_names[0]][0, :, :]
    else:
        varTmp = None
    MpiConfig.comm.barrier()

    varSubTmp = MpiConfig.scatter_array(supplemental_precip, varTmp, ConfigOptions)
    MpiConfig.comm.barrier()

    supplemental_precip.esmf_field_in.data[:, :] = varSubTmp
    MpiConfig.comm.barrier()

    supplemental_precip.esmf_field_out = supplemental_precip.regridObj(supplemental_precip.esmf_field_in,
                                                                       supplemental_precip.esmf_field_out)
    # Set any pixel cells outside the input domain to the global missing value.
    supplemental_precip.esmf_field_out.data[np.where(supplemental_precip.regridded_mask == 0)] = \
        ConfigOptions.globalNdv
    MpiConfig.comm.barrier()

    supplemental_precip.regridded_precip2[:, :] = \
        supplemental_precip.esmf_field_out.data
    MpiConfig.comm.barrier()

    # Check for any RQI values below the threshold specified by the user.
    # Set these values to global NDV.
    indFilter = np.where(supplemental_precip.regridded_rqi2 <= ConfigOptions.rqiThresh)
    supplemental_precip.regridded_precip2[indFilter] = ConfigOptions.globalNdv
    MpiConfig.comm.barrier()

    # Convert the hourly precipitation total to a rate of mm/s
    indValid = np.where(supplemental_precip.regridded_precip2 != ConfigOptions.globalNdv)
    supplemental_precip.regridded_precip2[indValid] = supplemental_precip.regridded_precip2[indValid]/3600.0
    # Reset index variables to free up memory
    indValid = None
    indFilter = None

    # If we are on the first timestep, set the previous regridded field to be
    # the latest as there are no states for time 0.
    if ConfigOptions.current_output_step == 1:
        supplemental_precip.regridded_precip1[:, :] = \
            supplemental_precip.regridded_precip2[:, :]
        supplemental_precip.regridded_rqi1[:, :] = \
            supplemental_precip.regridded_rqi2[:, :]
    MpiConfig.comm.barrier()

    # Close the temporary NetCDF file and remove it.
    if MpiConfig.rank == 0:
        try:
            idMrms.close()
        except:
            ConfigOptions.errMsg = "Unable to close NetCDF file: " + mrms_tmp_nc
            errMod.err_out(ConfigOptions)
        try:
            os.remove(mrms_tmp_nc)
        except:
            ConfigOptions.errMsg = "Unable to remove NetCDF file: " + mrms_tmp_nc
            errMod.err_out()

def regrid_hourly_WRF_ARW_HiRes_PCP(supplemental_precip,ConfigOptions,wrfHydroGeoMeta,MpiConfig):
    """
    Function for handling regridding hourly forecasted ARW precipitation for hi-res nests.
    :param supplemental_precip:
    :param ConfigOptions:
    :param wrfHydroGeoMeta:
    :param MpiConfig:
    :return:
    """
    # Check to see if the regrid complete flag for this
    # output time step is true. This entails the necessary
    # inputs have already been regridded and we can move on.
    if supplemental_precip.regridComplete:
        return

    if MpiConfig.rank == 0:
        print("REGRID STATUS = " + str(supplemental_precip.regridComplete))
    # Create a path for a temporary NetCDF files that will
    # be created through the wgrib2 process.
    arw_tmp_nc = ConfigOptions.scratch_dir + "/ARW_PCP_TMP.nc"
    MpiConfig.comm.barrier()

    # These files shouldn't exist. If they do, remove them.
    if MpiConfig.rank == 0:
        if os.path.isfile(arw_tmp_nc):
            ConfigOptions.statusMsg = "Found old temporary file: " + \
                                      arw_tmp_nc + " - Removing....."
            errMod.log_warning(ConfigOptions)
            try:
                os.remove(arw_tmp_nc)
            except:
                errMod.err_out(ConfigOptions)
    MpiConfig.comm.barrier()

    # If the input paths have been set to None, this means input is missing. We will
    # alert the user, and set the final output grids to be the global NDV and return.
    if not supplemental_precip.file_in1 or not supplemental_precip.file_in2:
        if MpiConfig.rank == 0:
            "NO ARW PRECIP AVAILABLE. SETTING FINAL SUPP GRIDS TO NDV"
        supplemental_precip.regridded_precip2 = None
        supplemental_precip.regridded_precip1 = None
        return
    MpiConfig.comm.barrier()

    # Create a temporary NetCDF file from the GRIB2 file.
    cmd = "wgrib2 " + supplemental_precip.file_in2 + " -match \":(" + \
          "APCP):(surface):(" + str(supplemental_precip.fcst_hour1) + \
          "-" + str(supplemental_precip.fcst_hour2) + " hour acc fcst):\"" + \
          " -netcdf " + arw_tmp_nc

    idTmp = ioMod.open_grib2(supplemental_precip.file_in2, arw_tmp_nc, cmd,
                             ConfigOptions, MpiConfig, "APCP_surface")
    MpiConfig.comm.barrier()

    # Check to see if we need to calculate regridding weights.
    calcRegridFlag = check_supp_pcp_regrid_status(idTmp, supplemental_precip,ConfigOptions,
                                                  MpiConfig, wrfHydroGeoMeta)
    MpiConfig.comm.barrier()

    if calcRegridFlag:
        if MpiConfig.rank == 0:
            print('CALCULATING ARW WEIGHTS')
        calculate_supp_pcp_weights(MpiConfig, ConfigOptions,
                                   supplemental_precip, idTmp, arw_tmp_nc)

    # Regrid the input variables.
    if MpiConfig.rank == 0:
        print("REGRIDDING: APCP_surface")
        varTmp = idTmp.variables['APCP_surface'][0, :, :]
    else:
        varTmp = None
    MpiConfig.comm.barrier()

    varSubTmp = MpiConfig.scatter_array(supplemental_precip, varTmp, ConfigOptions)
    MpiConfig.comm.barrier()

    supplemental_precip.esmf_field_in.data[:, :] = varSubTmp
    MpiConfig.comm.barrier()

    supplemental_precip.esmf_field_out = supplemental_precip.regridObj(supplemental_precip.esmf_field_in,
                                                                       supplemental_precip.esmf_field_out)
    # Set any pixel cells outside the input domain to the global missing value.
    supplemental_precip.esmf_field_out.data[np.where(supplemental_precip.regridded_mask == 0)] = \
        ConfigOptions.globalNdv
    MpiConfig.comm.barrier()

    supplemental_precip.regridded_precip2[:, :] = \
        supplemental_precip.esmf_field_out.data
    MpiConfig.comm.barrier()

    # Convert the hourly precipitation total to a rate of mm/s
    indValid = np.where(supplemental_precip.regridded_precip2 != ConfigOptions.globalNdv)
    supplemental_precip.regridded_precip2[indValid] = supplemental_precip.regridded_precip2[indValid]/3600.0
    # Reset index variables to free up memory
    indValid = None

    # If we are on the first timestep, set the previous regridded field to be
    # the latest as there are no states for time 0.
    if ConfigOptions.current_output_step == 1:
        supplemental_precip.regridded_precip1[:, :] = \
            supplemental_precip.regridded_precip2[:, :]
    MpiConfig.comm.barrier()

    # Close the temporary NetCDF file and remove it.
    if MpiConfig.rank == 0:
        try:
            idTmp.close()
        except:
            ConfigOptions.errMsg = "Unable to close NetCDF file: " + arw_tmp_nc
            errMod.err_out(ConfigOptions)
        try:
            os.remove(arw_tmp_nc)
        except:
            ConfigOptions.errMsg = "Unable to remove NetCDF file: " + arw_tmp_nc
            errMod.err_out()

def check_regrid_status(idTmp,forceCount,input_forcings,ConfigOptions,MpiConfig,wrfHydroGeoMeta):
    """
    Function for checking to see if regridding weights need to be
    calculated (or recalculated).
    :param input_forcings:
    :param ConfigOptions:
    :param MpiConfig:
    :return:
    """
    # If the destination ESMF field hasn't been created, create it here.
    if not input_forcings.esmf_field_out:
        try:
            input_forcings.esmf_field_out = ESMF.Field(wrfHydroGeoMeta.esmf_grid, name=input_forcings.productName + \
                                                                                       'FORCING_REGRIDDED')
        except:
            ConfigOptions.errMsg = "Unable to create " + input_forcings.productName + \
                                   " destination ESMF field object."
            errMod.err_out(ConfigOptions)

    # Determine if we need to calculate a regridding object. The following situations warrant the calculation of
    # a new weight file:
    # 1.) This is the first output time step, so we need to calculate a weight file.
    # 2.) The input forcing grid has changed.
    calcRegridFlag = False

    MpiConfig.comm.barrier()

    if input_forcings.nx_global == None or input_forcings.ny_global == None:
        # This is the first timestep.
        # Create out regridded numpy arrays to hold the regridded data.
        input_forcings.regridded_forcings1 = np.empty([8, wrfHydroGeoMeta.ny_local, wrfHydroGeoMeta.nx_local],
                                                      np.float32)
        input_forcings.regridded_forcings2 = np.empty([8, wrfHydroGeoMeta.ny_local, wrfHydroGeoMeta.nx_local],
                                                      np.float32)

    if MpiConfig.rank == 0:
        if input_forcings.nx_global == None or input_forcings.ny_global == None:
            # This is the first timestep.
            calcRegridFlag = True
        else:
            if MpiConfig.rank == 0:
                if idTmp.variables[input_forcings.netcdf_var_names[forceCount]].shape[1] \
                        != input_forcings.ny_global and \
                        idTmp.variables[input_forcings.netcdf_var_names[forceCount]].shape[2] \
                        != input_forcings.nx_global:
                    calcRegridFlag = True

    MpiConfig.comm.barrier()

    # Broadcast the flag to the other processors.
    calcRegridFlag = MpiConfig.broadcast_parameter(calcRegridFlag, ConfigOptions)

    MpiConfig.comm.barrier()
    return calcRegridFlag

def check_supp_pcp_regrid_status(idTmp,supplemental_precip,ConfigOptions,MpiConfig,wrfHydroGeoMeta):
    """
    Function for checking to see if regridding weights need to be
    calculated (or recalculated).
    :param input_forcings:
    :param ConfigOptions:
    :param MpiConfig:
    :return:
    """
    # If the destination ESMF field hasn't been created, create it here.
    if not supplemental_precip.esmf_field_out:
        try:
            supplemental_precip.esmf_field_out = ESMF.Field(wrfHydroGeoMeta.esmf_grid,
                                                            name=supplemental_precip.productName + \
                                                                 'SUPP_PCP_REGRIDDED')
        except:
            ConfigOptions.errMsg = "Unable to create " + supplemental_precip.productName + \
                                   " destination ESMF field object."
            errMod.err_out(ConfigOptions)

    # Determine if we need to calculate a regridding object. The following situations warrant the calculation of
    # a new weight file:
    # 1.) This is the first output time step, so we need to calculate a weight file.
    # 2.) The input forcing grid has changed.
    calcRegridFlag = False

    MpiConfig.comm.barrier()

    if supplemental_precip.nx_global == None or supplemental_precip.ny_global == None:
        # This is the first timestep.
        # Create out regridded numpy arrays to hold the regridded data.
        supplemental_precip.regridded_precip1 = np.empty([wrfHydroGeoMeta.ny_local, wrfHydroGeoMeta.nx_local],
                                                      np.float32)
        supplemental_precip.regridded_precip2 = np.empty([wrfHydroGeoMeta.ny_local, wrfHydroGeoMeta.nx_local],
                                                      np.float32)
        supplemental_precip.regridded_rqi1 = np.empty([wrfHydroGeoMeta.ny_local, wrfHydroGeoMeta.nx_local],
                                                      np.float32)
        supplemental_precip.regridded_rqi2 = np.empty([wrfHydroGeoMeta.ny_local, wrfHydroGeoMeta.nx_local],
                                                      np.float32)

    if MpiConfig.rank == 0:
        if supplemental_precip.nx_global == None or supplemental_precip.ny_global == None:
            # This is the first timestep.
            calcRegridFlag = True
        else:
            if MpiConfig.rank == 0:
                if idTmp.variables[supplemental_precip.netcdf_var_names[0]].shape[1] \
                        != supplemental_precip.ny_global and \
                        idTmp.variables[supplemental_precip.netcdf_var_names[0]].shape[2] \
                        != supplemental_precip.nx_global:
                    calcRegridFlag = True

    # We will now check to see if the regridded arrays are still None. This means the fields were set to None
    # earlier for missing data. We need to reset them to nx_global/ny_global where the calcRegridFlag is False.
    if supplemental_precip.regridded_precip2 == None:
        supplemental_precip.regridded_precip2 = np.empty([wrfHydroGeoMeta.ny_local, wrfHydroGeoMeta.nx_local],
                                                         np.float32)
    if supplemental_precip.regridded_precip1 == None:
        supplemental_precip.regridded_precip1 = np.empty([wrfHydroGeoMeta.ny_local, wrfHydroGeoMeta.nx_local],
                                                         np.float32)

    MpiConfig.comm.barrier()

    # Broadcast the flag to the other processors.
    calcRegridFlag = MpiConfig.broadcast_parameter(calcRegridFlag, ConfigOptions)

    MpiConfig.comm.barrier()
    return calcRegridFlag

def calculate_weights(MpiConfig,ConfigOptions,forceCount,input_forcings,idTmp):
    """
    Function to calculate ESMF weights based on the output ESMF
    field previously calculated, along with input lat/lon grids,
    and a sample dataset.
    :param MpiConfig:
    :param ConfigOptions:
    :param forceCount:
    :return:
    """
    if MpiConfig.rank == 0:
        try:
            input_forcings.ny_global = \
                idTmp.variables[input_forcings.netcdf_var_names[forceCount]].shape[1]
        except:
            ConfigOptions.errMsg = "Unable to extract Y shape size from: " + \
                                   input_forcings.netcdf_var_names[forceCount] + " from: " + \
                                   input_forcings.tmpFile
            errMod.err_out(ConfigOptions)
        try:
            input_forcings.nx_global = \
                idTmp.variables[input_forcings.netcdf_var_names[forceCount]].shape[2]
        except:
            ConfigOptions.errMsg = "Unable to extract X shape size from: " + \
                                   input_forcings.netcdf_var_names[forceCount] + " from: " + \
                                   input_forcings.tmpFile
            errMod.err_out(ConfigOptions)
    MpiConfig.comm.barrier()

    # Broadcast the forcing nx/ny values
    input_forcings.ny_global = MpiConfig.broadcast_parameter(input_forcings.ny_global,
                                                             ConfigOptions)
    input_forcings.nx_global = MpiConfig.broadcast_parameter(input_forcings.nx_global,
                                                             ConfigOptions)
    MpiConfig.comm.barrier()

    try:
        input_forcings.esmf_grid_in = ESMF.Grid(np.array([input_forcings.ny_global, input_forcings.nx_global]),
                                                staggerloc=ESMF.StaggerLoc.CENTER,
                                                coord_sys=ESMF.CoordSys.SPH_DEG)
    except:
        ConfigOptions.errMsg = "Unable to create source GFS ESMF grid from temporary file: " + \
                               input_forcings.tmpFile
        errMod.err_out(ConfigOptions)
    MpiConfig.comm.barrier()

    try:
        input_forcings.x_lower_bound = input_forcings.esmf_grid_in.lower_bounds[ESMF.StaggerLoc.CENTER][1]
        input_forcings.x_upper_bound = input_forcings.esmf_grid_in.upper_bounds[ESMF.StaggerLoc.CENTER][1]
        input_forcings.y_lower_bound = input_forcings.esmf_grid_in.lower_bounds[ESMF.StaggerLoc.CENTER][0]
        input_forcings.y_upper_bound = input_forcings.esmf_grid_in.upper_bounds[ESMF.StaggerLoc.CENTER][0]
        #print('PROC: ' + str(MpiConfig.rank) + ' GFS XBOUND1 = ' + str(input_forcings.x_lower_bound))
        #print('PROC: ' + str(MpiConfig.rank) + ' GFS XBOUND2 = ' + str(input_forcings.x_upper_bound))
        #print('PROC: ' + str(MpiConfig.rank) + ' GFS YBOUND1 = ' + str(input_forcings.y_lower_bound))
        #print('PROC: ' + str(MpiConfig.rank) + ' GFS YBOUND2 = ' + str(input_forcings.y_upper_bound))
        input_forcings.nx_local = input_forcings.x_upper_bound - input_forcings.x_lower_bound
        input_forcings.ny_local = input_forcings.y_upper_bound - input_forcings.y_lower_bound
    except:
        ConfigOptions.errMsg = "Unable to extract local X/Y boundaries from global grid from temporary " + \
                               "file: " + input_forcings.tmpFile
        errMod.err_out(ConfigOptions)
    MpiConfig.comm.barrier()

    if MpiConfig.rank == 0:
        # Process lat/lon values from the GFS grid.
        if len(idTmp.variables['latitude'].shape) == 3:
            # We have 2D grids already in place.
            latTmp = idTmp.variables['latitude'][0, :, :]
            lonTmp = idTmp.variables['longitude'][0, :, :]
        elif len(idTmp.variables['longitude'].shape) == 2:
            # We have 2D grids already in place.
            latTmp = idTmp.variables['latitude'][:, :]
            lonTmp = idTmp.variables['longitude'][:, :]
        elif len(idTmp.variables['latitude'].shape) == 1:
            # We have 1D lat/lons we need to translate into
            # 2D grids.
            latTmp = np.repeat(idTmp.variables['latitude'][:][:, np.newaxis], input_forcings.nx_global, axis=1)
            lonTmp = np.tile(idTmp.variables['longitude'][:], (input_forcings.ny_global, 1))
    MpiConfig.comm.barrier()

    # Scatter global GFS latitude grid to processors..
    if MpiConfig.rank == 0:
        varTmp = latTmp
    else:
        varTmp = None
    varSubLatTmp = MpiConfig.scatter_array(input_forcings, varTmp, ConfigOptions)
    MpiConfig.comm.barrier()

    if MpiConfig.rank == 0:
        varTmp = lonTmp
    else:
        varTmp = None
    varSubLonTmp = MpiConfig.scatter_array(input_forcings, varTmp, ConfigOptions)
    MpiConfig.comm.barrier()

    try:
        input_forcings.esmf_lats = input_forcings.esmf_grid_in.get_coords(1)
    except:
        ConfigOptions.errMsg = "Unable to locate latitude coordinate object within input GFS ESMF grid."
        errMod.err_out(ConfigOptions)
    MpiConfig.comm.barrier()

    try:
        input_forcings.esmf_lons = input_forcings.esmf_grid_in.get_coords(0)
    except:
        ConfigOptions.errMsg = "Unable to locate longitude coordinate object within input GFS ESMF grid."
        errMod.err_out(ConfigOptions)
    MpiConfig.comm.barrier()

    input_forcings.esmf_lats[:, :] = varSubLatTmp
    input_forcings.esmf_lons[:, :] = varSubLonTmp
    varSubLatTmp = None
    varSubLonTmp = None
    latTmp = None
    lonTmp = None

    # Create a ESMF field to hold the incoming data.
    input_forcings.esmf_field_in = ESMF.Field(input_forcings.esmf_grid_in, name=input_forcings.productName + \
                                                                                "_NATIVE")

    MpiConfig.comm.barrier()

    # Scatter global grid to processors..
    if MpiConfig.rank == 0:
        varTmp = idTmp[input_forcings.netcdf_var_names[forceCount]][0, :, :]
        # Set all valid values to 1.0, and all missing values to 0.0. This will
        # be used to generate an output mask that is used later on in downscaling, layering,
        # etc.
        varTmp[:,:] = 1.0
    else:
        varTmp = None
    varSubTmp = MpiConfig.scatter_array(input_forcings, varTmp, ConfigOptions)
    MpiConfig.comm.barrier()

    # Place temporary data into the field array for generating the regridding object.
    input_forcings.esmf_field_in.data[:, :] = varSubTmp
    MpiConfig.comm.barrier()

    if MpiConfig.rank == 0:
        print("CREATING REGRID OBJECT")
    input_forcings.regridObj = ESMF.Regrid(input_forcings.esmf_field_in,
                                           input_forcings.esmf_field_out,
                                           src_mask_values=np.array([0]),
                                           regrid_method=ESMF.RegridMethod.BILINEAR,
                                           unmapped_action=ESMF.UnmappedAction.IGNORE)

    # Run the regridding object on this test dataset. Check the output grid for
    # any 0 values.
    input_forcings.esmf_field_out = input_forcings.regridObj(input_forcings.esmf_field_in,
                                                             input_forcings.esmf_field_out)
    input_forcings.regridded_mask[:, :] = input_forcings.esmf_field_out.data[:, :]

def calculate_supp_pcp_weights(MpiConfig,ConfigOptions,supplemental_precip,idTmp,tmpFile):
    """
    Function to calculate ESMF weights based on the output ESMF
    field previously calculated, along with input lat/lon grids,
    and a sample dataset.
    :param MpiConfig:
    :param ConfigOptions:
    :param forceCount:
    :return:
    """
    if MpiConfig.rank == 0:
        try:
            supplemental_precip.ny_global = \
                idTmp.variables[supplemental_precip.netcdf_var_names[0]].shape[1]
        except:
            ConfigOptions.errMsg = "Unable to extract Y shape size from: " + \
                                   supplemental_precip.netcdf_var_names[0] + " from: " + \
                                   tmpFile
            errMod.err_out(ConfigOptions)
        try:
            supplemental_precip.nx_global = \
                idTmp.variables[supplemental_precip.netcdf_var_names[0]].shape[2]
        except:
            ConfigOptions.errMsg = "Unable to extract X shape size from: " + \
                                   supplemental_precip.netcdf_var_names[0] + " from: " + \
                                   tmpFile
            errMod.err_out(ConfigOptions)
    MpiConfig.comm.barrier()

    # Broadcast the forcing nx/ny values
    supplemental_precip.ny_global = MpiConfig.broadcast_parameter(supplemental_precip.ny_global,
                                                             ConfigOptions)
    supplemental_precip.nx_global = MpiConfig.broadcast_parameter(supplemental_precip.nx_global,
                                                             ConfigOptions)
    MpiConfig.comm.barrier()

    try:
        supplemental_precip.esmf_grid_in = ESMF.Grid(np.array([supplemental_precip.ny_global,
                                                               supplemental_precip.nx_global]),
                                                     staggerloc=ESMF.StaggerLoc.CENTER,
                                                     coord_sys=ESMF.CoordSys.SPH_DEG)
    except:
        ConfigOptions.errMsg = "Unable to create source ESMF grid from temporary file: " + \
                               tmpFile
        errMod.err_out(ConfigOptions)
    MpiConfig.comm.barrier()

    try:
        supplemental_precip.x_lower_bound = supplemental_precip.esmf_grid_in.lower_bounds[ESMF.StaggerLoc.CENTER][1]
        supplemental_precip.x_upper_bound = supplemental_precip.esmf_grid_in.upper_bounds[ESMF.StaggerLoc.CENTER][1]
        supplemental_precip.y_lower_bound = supplemental_precip.esmf_grid_in.lower_bounds[ESMF.StaggerLoc.CENTER][0]
        supplemental_precip.y_upper_bound = supplemental_precip.esmf_grid_in.upper_bounds[ESMF.StaggerLoc.CENTER][0]
        #print('PROC: ' + str(MpiConfig.rank) + ' SUPP PCP XBOUND1 = ' + str(supplemental_precip.x_lower_bound))
        #print('PROC: ' + str(MpiConfig.rank) + ' SUPP PCP XBOUND2 = ' + str(supplemental_precip.x_upper_bound))
        #print('PROC: ' + str(MpiConfig.rank) + ' SUPP PCP YBOUND1 = ' + str(supplemental_precip.y_lower_bound))
        #print('PROC: ' + str(MpiConfig.rank) + ' SUPP PCP YBOUND2 = ' + str(supplemental_precip.y_upper_bound))
        supplemental_precip.nx_local = supplemental_precip.x_upper_bound - supplemental_precip.x_lower_bound
        supplemental_precip.ny_local = supplemental_precip.y_upper_bound - supplemental_precip.y_lower_bound
    except:
        ConfigOptions.errMsg = "Unable to extract local X/Y boundaries from global grid from temporary " + \
                               "file: " + tmpFile
        errMod.err_out(ConfigOptions)
    MpiConfig.comm.barrier()

    if MpiConfig.rank == 0:
        # Process lat/lon values from the GFS grid.
        if len(idTmp.variables['latitude'].shape) == 3:
            # We have 2D grids already in place.
            latTmp = idTmp.variables['latitude'][0, :, :]
            lonTmp = idTmp.variables['longitude'][0, :, :]
        elif len(idTmp.variables['longitude'].shape) == 2:
            # We have 2D grids already in place.
            latTmp = idTmp.variables['latitude'][:, :]
            lonTmp = idTmp.variables['longitude'][:, :]
        elif len(idTmp.variables['latitude'].shape) == 1:
            # We have 1D lat/lons we need to translate into
            # 2D grids.
            latTmp = np.repeat(idTmp.variables['latitude'][:][:, np.newaxis], supplemental_precip.nx_global, axis=1)
            lonTmp = np.tile(idTmp.variables['longitude'][:], (supplemental_precip.ny_global, 1))
    MpiConfig.comm.barrier()

    # Scatter global GFS latitude grid to processors..
    if MpiConfig.rank == 0:
        varTmp = latTmp
    else:
        varTmp = None
    varSubLatTmp = MpiConfig.scatter_array(supplemental_precip, varTmp, ConfigOptions)
    MpiConfig.comm.barrier()

    if MpiConfig.rank == 0:
        varTmp = lonTmp
    else:
        varTmp = None
    varSubLonTmp = MpiConfig.scatter_array(supplemental_precip, varTmp, ConfigOptions)
    MpiConfig.comm.barrier()

    try:
        supplemental_precip.esmf_lats = supplemental_precip.esmf_grid_in.get_coords(1)
    except:
        ConfigOptions.errMsg = "Unable to locate latitude coordinate object within supplemental precip ESMF grid."
        errMod.err_out(ConfigOptions)
    MpiConfig.comm.barrier()

    try:
        supplemental_precip.esmf_lons = supplemental_precip.esmf_grid_in.get_coords(0)
    except:
        ConfigOptions.errMsg = "Unable to locate longitude coordinate object within supplemental precip ESMF grid."
        errMod.err_out(ConfigOptions)
    MpiConfig.comm.barrier()

    supplemental_precip.esmf_lats[:, :] = varSubLatTmp
    supplemental_precip.esmf_lons[:, :] = varSubLonTmp
    varSubLatTmp = None
    varSubLonTmp = None
    latTmp = None
    lonTmp = None

    # Create a ESMF field to hold the incoming data.
    supplemental_precip.esmf_field_in = ESMF.Field(supplemental_precip.esmf_grid_in,
                                                   name=supplemental_precip.productName + \
                                                        "_NATIVE")

    MpiConfig.comm.barrier()

    # Scatter global grid to processors..
    if MpiConfig.rank == 0:
        varTmp = idTmp[supplemental_precip.netcdf_var_names[0]][0, :, :]
        # Set all valid values to 1.0, and all missing values to 0.0. This will
        # be used to generate an output mask that is used later on in downscaling, layering,
        # etc.
        varTmp[:,:] = 1.0
    else:
        varTmp = None
    varSubTmp = MpiConfig.scatter_array(supplemental_precip, varTmp, ConfigOptions)
    MpiConfig.comm.barrier()

    # Place temporary data into the field array for generating the regridding object.
    supplemental_precip.esmf_field_in.data[:, :] = varSubTmp
    MpiConfig.comm.barrier()

    if MpiConfig.rank == 0:
        print("CREATING SUPPLEMENTAL PRECIP REGRID OBJECT")
    supplemental_precip.regridObj = ESMF.Regrid(supplemental_precip.esmf_field_in,
                                                supplemental_precip.esmf_field_out,
                                                src_mask_values=np.array([0]),
                                                regrid_method=ESMF.RegridMethod.BILINEAR,
                                                unmapped_action=ESMF.UnmappedAction.IGNORE)

    # Run the regridding object on this test dataset. Check the output grid for
    # any 0 values.
    supplemental_precip.esmf_field_out = supplemental_precip.regridObj(supplemental_precip.esmf_field_in,
                                                                       supplemental_precip.esmf_field_out)
    supplemental_precip.regridded_mask[:, :] = supplemental_precip.esmf_field_out.data[:, :]