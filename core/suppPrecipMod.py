"""
High-level module file that will handle supplemental analysis/observed precipitation grids
that will replace precipitation in the final output files.
"""
from core import dateMod
from core import regridMod
import numpy as np
from core import timeInterpMod
import os
from core import errMod

class supplemental_precip:
    """
    This is an abstract class that will define all the parameters
    of a single supplemental precipitation product.
    """
    def __init__(self):
        """
        Initializing all attributes and objects to None.
        """
        self.keyValue = None
        self.inDir = None
        self.productName = None
        self.fileType = None
        self.nx_global = None
        self.ny_global = None
        self.nx_local = None
        self.ny_local = None
        self.x_lower_bound = None
        self.x_upper_bound = None
        self.y_lower_bound = None
        self.y_upper_bound = None
        self.regridOpt = None
        self.timeInterpOpt = None
        self.esmf_lats = None
        self.esmf_lons = None
        self.esmf_grid_in = None
        self.regridComplete = False
        self.regridObj = None
        self.esmf_field_in = None
        self.esmf_field_out = None
        self.regridded_precip1 = None
        self.regridded_precip2 = None
        self.regridded_mask = None
        self.final_supp_precip = None
        self.file_in1 = None
        self.file_in2 = None
        self.pcp_hour1 = None
        self.pcp_hour2 = None
        self.pcp_date1 = None
        self.pcp_date2 = None
        self.netcdf_var_names = None
        self.grib_levels = None
        self.grib_vars = None
        self.tmpFile = None

    def define_product(self):
        """
        Function to define the product name based on the mapping
        forcing key value.
        :return:
        """
        product_names = {
            1: "MRMS_1HR_Radar_Only",
            2: "MRMS_1HR_Gage_Corrected"
        }
        self.productName = product_names[self.keyValue]

        product_types = {
            1: "GRIB2",
            2: "GRIB2"
        }
        self.fileType = product_types[self.keyValue]

        grib_vars_in = {
            1: ['BLAH'],
            2: ['BLAH']
        }
        self.grib_vars = grib_vars_in[self.keyValue]

        grib_levels_in = {
            1: ['BLAH'],
            2: ['BLAH']
        }
        self.grib_levels = grib_levels_in[self.keyValue]

        netcdf_variables = {
            1: None,
            2: None
        }
        self.netcdf_var_names = netcdf_variables[self.keyValue]

    def calc_neighbor_files(self,ConfigOptions,dCurrent,MpiConfig):
        """
        Function that will calculate the last/next expected
        supplemental precipitation file based on the current time step that
        is being processed.
        :param ConfigOptions:
        :param dCurrent:
        :return:
        """
        # First calculate the current input cycle date this
        # WRF-Hydro output timestep corresponds to.
        find_neighbor_files = {
            1: dateMod.find_gfs_neighbors
        }

        find_neighbor_files[self.keyValue](self, ConfigOptions, dCurrent, MpiConfig)
        # try:
        #    find_neighbor_files[self.keyValue](self,ConfigOptions,dCurrent,MpiConfig)
        # except TypeError:
        #    ConfigOptions.errMsg = "Unable to execute find_neighbor_files for " \
        #                           "supplemental precipitation: " + self.productName
        #    raise
        # except:
        #    raise

def initDict(ConfigOptions):
    """
    Initial function to create an supplemental dictionary, which
    will contain an abstract class for each supplemental precip product.
    This gets called one time by the parent calling program.
    :param ConfigOptions:
    :return: InputDict - A dictionary defining our inputs.
    """
    # Initialize an empty dictionary
    InputDict = {}

    for supp_pcp_tmp in range(0,ConfigOptions.number_supp_pcp):
        supp_pcp_key = ConfigOptions.supp_precip_forcings[supp_pcp_tmp]
        InputDict[supp_pcp_key] = supplemental_precip()
        InputDict[supp_pcp_key].keyValue = supp_pcp_key
        InputDict[supp_pcp_key].regridOpt = ConfigOptions.regrid_opt_supp_pcp[supp_pcp_tmp]
        InputDict[supp_pcp_key].timeInterpOpt = ConfigOptions.suppTemporalInterp[supp_pcp_tmp]

        InputDict[supp_pcp_key].inDir = ConfigOptions.supp_precip_dirs[supp_pcp_tmp]
        InputDict[supp_pcp_key].define_product()

    return InputDict

