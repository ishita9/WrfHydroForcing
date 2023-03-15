#Module provides a template of yaml comment headers to insert for each section of 
#auto-generated yaml config

comments = {
'Header' : 
"""#Document start
---
# WRF-Hydro Forcing Engine YAML Configuration File
#
# Input options to the forcing engine include:
# 1.) Choices for input forcing files to use.
# 2.) Options for specifying date ranges and forecast intervals
#     for input files.
# 3.) Choices for ESMF regridding techniques.
# 4.) Choices for optional downscaling techniques.
# 5.) Choices for optional bias correction techniques.
# 6.) Choices for optional supplemental precipitation products.
# 7.) Choices for optional ensemble member variations.
# 8.) Choices for output directories to place final output files.""",
'Input' : 
"""#Input Example With Two Separate Inputs (a YAML list of input parameters)
#
#Input:
# - Forcing: RAP
#   Type: GRIB2
#   Dir: /glade/p/ral/allral/zhangyx/RAP_Conus
#   Mandatory: True
#   Horizon: 60
#   Offset: 0
#   IgnoredBorderWidths: 0
#   RegriddingOpt: ESMF_BILINEAR
#   TemporalInterp: NONE
##   Custom:
##    input_fcst_freq: 60
#   BiasCorrection:
#    Temperature: NONE
#    Pressure: NONE
#    Humidity: NONE
#    Wind: NONE
#    Shortwave: NONE
#    Longwave: NONE
#    Precip: NONE
#   Downscaling:
#    Temperature: LAPSE_PRE_CALC
#    Pressure: ELEV
#    Shortwave: ELEV
#    Precip: NONE
#    Humidity: REGRID_TEMP_PRESS
#    ParamDir: /glade/p/cisl/nwc/nwm_forcings/NWM_v21_Params/AnA
# - Forcing: HRRR
#   Type: GRIB2
#   Dir: /glade/p/ral/allral/zhangyx/HRRR_Conus
#   Mandatory: True
#   Horizon: 60
#   Offset: 0
#   IgnoredBorderWidths: 5
#   RegriddingOpt: ESMF_BILINEAR
#   TemporalInterp: NONE
#   BiasCorrection:
#    Temperature: HRRR
#    Pressure: NONE
#    Humidity: NONE
#    Wind: HRRR
#    Shortwave: CUSTOM
#    Longwave: CUSTOM
#    Precip: NONE
#   Downscaling:
#    Temperature: LAPSE_PRE_CALC
#    Pressure: ELEV
#    Shortwave: ELEV
#    Precip: NONE
#    Humidity: REGRID_TEMP_PRESS
#    ParamDir: /glade/p/cisl/nwc/nwm_forcings/NWM_v21_Params/AnA
#
#Input[i]['Forcing']
# Choose a set of value(s) of forcing variables to be processed for
# WRF-Hydro. Please be advised that the order of which the values are
# chosen below are the order that the final products will be layered
# into the final LDASIN files. See documentation for additional
# information and examples.
# The following is a global set of key values to map forcing files
# to variables within LDASIN files for WRF-Hydro. The forcing engine
# will map files to external variable names internally. For custom
# external native forcing files (see documenation), the code will
# expect a set of named variables to process.
# NLDAS - GRIB retrospective files
# NARR - GRIB retrospective files
# GFS_GLOBAL - GRIB2 Global production files on the full gaussian grid
# NAM_NEST_CONUS - Nest GRIB2 Conus production files
# HRRR - GRIB2 Conus production files
# RAP - GRIB2 Conus 13km production files
# CFS_V2 - 6-hourly GRIB2 Global production files
# WRF_NEST_HI - GRIB2 Hawaii nest files
# GFS_GLOBAL_25 - GRIB2 Global production files on 0.25 degree lat/lon grids.
# CUSTOM_1 - Custom NetCDF hourly forcing files
# CUSTOM_2 - NetCDF hourly forcing files
# CUSTOM_3 - NetCDF hourly forcing files
# NAM_NEST_HI - 3-km NAM Nest.
# NAM_NEST_PR - 3-km NAM Nest.
# NAM_NEST_AK - 3-km Alaska Nest
# NAM_NEST_HI_RAD - NAM_Nest_3km_Hawaii_Radiation-Only
# NAM_NEST_PR_RAD - NAM_Nest_3km_PuertoRico_Radiation-Only
# WRF_ARW_PR - GRIB2 PuertoRico
#
#Input[i]['Type']
# Specify the file type for each forcing
# GRIB
# GRIB2
# NETCDF
# (GRIB files will be converted internally with WGRIB[2])
#
#Input[i]['Dir']
# Specify the input directories for each forcing product.
#
#Input[i]['Mandatory']
# Specify whether the input forcings listed above are mandatory, or optional.
# This is important for layering contingencies if a product is missing,
# but forcing files are still desired.
# False - Not mandatory
# True - Mandatory
# NOTE!!! If not files are found for any products, code will error out indicating
# the final field is all missing values.
#
#Input[i]['Horizon']
#Specify how much (in minutes) of each input forcing is desires for each
# forecast cycle. See documentation for examples. The length of
# this array must match the input forcing choices.
#
#Input[i]['Offset']
# This option is for applying an offset to input forcings to use a different
# forecasted interval. For example, a user may wish to use 4-5 hour forecasted
# fields from an NWP grid from one of their input forcings. In that instance
# the offset would be 4 hours, but 0 for other remaining forcings.
#
# In AnA runs, this value is the offset from the available forecast and 00z
# For example, if forecast are available at 06z and 18z, set this value to 6
#
# Input[i]['IgnoredBorderWidths']
# Specify a border width (in grid cells) to ignore for each input dataset.
# NOTE: generally, the first input forcing should always be zero or there will be missing data in the final output
#
# Input[i]['RegriddingOpt']
# Choose regridding options for each input forcing files being used. Options available are:
# ESMF_BILINEAR
# ESMF_NEAREST_NEIGHBOR
# ESMF_CONSERVATIVE_BILINEAR
#
# Input[i]['TemporalInterp']
# Specify an temporal interpolation for the forcing variables.
# Interpolation will be done between the two neighboring
# input forcing states that exist. If only one nearest
# state exist (I.E. only a state forward in time, or behind),
# then that state will be used as a "nearest neighbor".
# NOTE - All input options here must be of the same length
# of the input forcing number. Also note all temporal interpolation
# occurs BEFORE downscaling and bias correction.
# NONE - No temporal interpolation.
# NEAREST_NEIGHBOR - Nearest Neighbor
# LINEAR_WEIGHT_AVG - Linear weighted average
#
# (Optional)
# Input[i]['Custom']['input_fcst_freq']
# These are options for specifying custom input NetCDF forcing files (in minutes).
# Choose the input frequency of files that are being processed. I.E., are the
# input files every 15 minutes, 60 minutes, 3-hours, etc. Please specify the
# length of custom input frequencies to match the number of custom NetCDF inputs
# selected above in the Logistics section.
#
# Choose bias correction options for each of the input forcing files.
#
# Input[i]['BiasCorrection']['Temperature']
# Specify a temperature bias correction method.
# NONE - No bias correction
# CFS_V2 - CFSv2 - NLDAS2 Parametric Distribution - NWM ONLY
# CUSTOM - Custom NCAR bias-correction based on HRRRv3 analysis - based on hour of day (USE WITH CAUTION).
# GFS - NCAR parametric GFS bias correction
# HRRR - NCAR parametric HRRR bias correction
#
# Input[i]['BiasCorrection]['Pressure']
# Specify a surface pressure bias correction method.
# NONE - No bias correction.
# CFS_V2 - CFSv2 - NLDAS2 Parametric Distribution - NWM ONLY
#
# Input[i]['BiasCorrection']['Humidity']
# Specify a specific humidity bias correction method.
# NONE - No bias correction.
# CFS_V2 - CFSv2 - NLDAS2 Parametric Distribution - NWM ONLY
# CUSTOM - Custom NCAR bias-correction based on HRRRv3 analysis - based on hour of day (USE WITH CAUTION).
#
# Input[i]['BiasCorrection']['Wind']
# Specify a wind bias correction.
# NONE - No bias correction.
# CFS_V2 - CFSv2 - NLDAS2 Parametric Distribution - NWM ONLY
# CUSTOM - Custom NCAR bias-correction based on HRRRv3 analysis - based on hour of day (USE WITH CAUTION).
# GFS - NCAR parametric GFS bias correction
# HRRR - NCAR parametric HRRR bias correction
#
# Input[i]['BiasCorrection']['Shortwave']
# Specify a bias correction for incoming short wave radiation flux.
# NONE - No bias correction.
# CFS_V2 - CFSv2 - NLDAS2 Parametric Distribution - NWM ONLY
# CUSTOM - Custom NCAR bias-correction based on HRRRv3 analysis (USE WITH CAUTION).
#
# Input[i]['BiasCorrection']['Longwave']
# Specify a bias correction for incoming long wave radiation flux.
# NONE - No bias correction.
# CFS_V2 - CFSv2 - NLDAS2 Parametric Distribution - NWM ONLY
# CUSTOM - Custom NCAR bias-correction based on HRRRv3 analysis, blanket adjustment (USE WITH CAUTION).
# GFS - NCAR parametric GFS bias correction
#
# Input[i]['BiasCorrection']['Precip']
# Specify a bias correction for precipitation.
# NONE - No bias correction.
# CFS_V2 - CFSv2 - NLDAS2 Parametric Distribution - NWM ONLY
#
# Choose downscaling options for each of the input forcing files. Length of each option
# must match the length of input forcings.
#
# Input[i]['Downscaling']['Temperature']
# Specify a temperature downscaling method:
# NONE - No downscaling.
# LAPSE_675 - Use a simple lapse rate of 6.75 degrees Celsius to get from the model elevation to the WRF-Hydro elevation.
# LAPSE_PRE_CALC - Use a pre-calculated lapse rate regridded to the WRF-Hydro domain.
#
# Input[i]['Downscaling']['Pressure']
# Specify a surface pressure downscaling method:
# NONE - No downscaling.
# ELEV - Use input elevation and WRF-Hydro elevation to downscale surface pressure.
#
# Input[i]['Downscaling']['Shortwave']
# Specify a shortwave radiation downscaling routine.
# NONE - No downscaling
# ELEV - Run a topographic adjustment using the WRF-Hydro elevation
#
# Input[i]['Downscaling']['Precip']
# Specify a precipitation downscaling routine.
# NONE - No downscaling
# NWM_MM - NWM mountain mapper downscaling using monthly PRISM climo.
#
# Input[i]['Downscaling']['Humidity']
# Specify a specific humidity downscaling routine.
# NONE - No downscaling
# REGRID_TEMP_PRESS - Use regridded humidity, along with downscaled temperature/pressure to extrapolate a downscaled surface specific humidty.
#
# Input[i]['Downscaling']['ParamDir']
# Specify the input parameter directory containing necessary downscaling grids.""",
'Output' : 
"""#Output Example
#
#Output:
# Frequency: 60
# Dir: /glade/scratch/bpetzke/ForcingEngine/Test/AnA
# ScratchDir: /glade/scratch/bpetzke/ForcingEngine/Test/AnA
# FloatOutput: SCALE_OFFSET
# CompressOutput: False
#
#Output['Frequency']
# Specify the output frequency in minutes.
# Note that any frequencies at higher intervals
# than what is provided as input will entail input
# forcing data being temporally interpolated.
#
#Output['Dir']
# Specify a top level output directory. For re-forecasts
# and forecasts, sub-directories for each forecast cycle
# will be generated. For retrospective processing, final
# output files will be placed in this directory.
#
#Output['ScratchDir']
# Specify a scratch directory that will be used
# for storage of temporary files. These files
# will be removed automatically by the program.
#
#Output['FloatOutput']
# Flag to use floating point output vs scale_factor / add_offset byte packing in
# the output files (the default)
# SCALE_OFFSET - Use scale/offset encoding
# FLOAT - Use floating-point encoding
#
#Output['CompressOutput']
# Flag to activate netCDF4 deflate compression in the output files.
# False - Deactivate compression
# True - Activate compression
""",
'Retrospective' : 
"""#Retrospective Example
#
# Retrospective:
#  Flag: False
#  BDateProc: 202002040000
#  EDateProc: 202002050000
#
#Retrospective['Flag']
# Specify to process forcings in retrosective mode
# False - No
# True - Yes
#
#Retrospective['BDateProc']
#Retrospective['EDateProc']
# Choose the beginning date of processing forcing files.
# NOTE - Dates are given in YYYYMMDDHHMM format
# If in real-time forecasting mode, leave as -9999.
# These dates get over-ridden in lookBackHours.""",
'Forecast' : 
"""#Forecast Example
#
# Forecast:
#  AnAFlag: True
#  LookBack: 180
#  RefcstBDateProc: 202009152300
#  RefcstEDateProc: 202009160000
#  Frequency: 60
#  Shift: 0
#
# Forecast['AnAFlag']
# Specify if this is an Analysis and Assimilation run (AnA).
# True - AnA run
# False
# Setting this flag will change the behavior of some Bias Correction routines as wel
# as the ForecastInputOffsets options (see below for more information)
#
#Forecast['LookBack']
# ONLY for realtime forecasting.
# Specify a lookback period in minutes to process data.
# This overrides any BDateProc/EDateProc options passed above.
# If no LookBack specified, please specify -9999.
#
#Forecast['RefcstBDateProc']
#Forecast['RefcstEDateProc']
# If running reforecasts, specify a window below. This will override
# using the LookBack value to calculate a processing window.
#
#Forecast['Frequency']
# Specify a forecast frequency in minutes. This value specifies how often
# to generate a set of forecast forcings. If generating hourly retrospective
# forcings, specify this value to be 60. =
#
#Forecast['Shift']
# Forecast cycles are determined by splitting up a day by equal
# ForecastFrequency interval. If there is a desire to shift the
# cycles to a different time step, ForecastShift will shift forecast
# cycles ahead by a determined set of minutes. For example, ForecastFrequency
# of 6 hours will produce forecasts cycles at 00, 06, 12, and 18 UTC. However,
# a ForecastShift of 1 hour will produce forecast cycles at 01, 07,
# 13, and 18 UTC. NOTE - This is only used by the realtime instance
# to calculate forecast cycles accordingly. Re-forecasts will use the beginning
# and ending dates specified in conjunction with the forecast frequency
# to determine forecast cycle dates.""",
'Geospatial' : 
"""#Geospatial Example
#
# Geospatial:
#  GeogridIn: /glade/p/cisl/nwc/nwmv20_finals/CONUS/DOMAIN/geo_em.d01.conus_1km_NWMv2.0.nc
#  SpatialMetaIn: /glade/p/cisl/nwc/nwmv20_finals/CONUS/DOMAIN/GEOGRID_LDASOUT_Spatial_Metadata_1km_NWMv2.0.nc
#
# Geospatial['GeogridIn']
# Specify a geogrid file that defines the WRF-Hydro (or NWM) domain to which
# the forcings are being processed to.
#
# Geospatial['SpatialMetaIn']
# Specify the optional land spatial metadata file. If found, coordinate projection information
# and coordinate will be translated from to the final output file.""",
'Regridding' : 
"""#Regridding Example
#
# Regridding:
#  WeightsDir: /glade/p/cisl/nwc/nwm_forcings/ESMFWeightFiles""",
'SuppForcing' : 
"""# SuppForcing Example
#
#SuppForcing:
# - Pcp: MRMR_CONUS_MS
#   PcpTypes: GRIB2
#   PcpDir: /glade/p/ral/allral/zhangyx/CONUS.MRMS
#   PcpMandatory: False
#   RegridOptPcp: 1
#   PcpTemporalInterpolation: 0
#   PcpInputOffsets: 0
#   RqiMethod: NWM
#   RqiThreshold: 0.9
#   PcpParamDir: /glade/p/cisl/nwc/nwm_forcings/NWM_v21_Params/AnA
#
# SuppForcing[i]['Pcp']
# Choose a set of supplemental precipitation file(s) to layer
# into the final LDASIN forcing files processed from
# the options above. The following is a mapping of
# numeric values to external input native forcing files:
# MRMS - MRMS GRIB2 hourly radar-only QPE
# MRMS_GAGE - MRMS GRIB2 hourly gage-corrected radar QPE
# WRF_ARW_HI - WRF-ARW 2.5 km 48-hr Hawaii nest precipitation.
# WRF_ARW_PR - WRF-ARW 2.5 km 48-hr Puerto Rico nest precipitation.
# MRMS_CONUS_MS - CONUS MRMS MultiSensor Pass1 and Pass1
# MRMS_HI_MS - Hawaii MRMS MultiSensor Pass1 and Pass2
# MRMS_SBCV2 - Liquid Water Fraction (netCDF only)
#
# SuppForcing[i]['PcpType']
# Specify the file type for each supplemental precipitation file (comma separated)
# GRIB1
# GRIB2
# NETCDF
# (GRIB files will be converted internally with WGRIB[2])
#
# SupportForcing[i]['PcpDir']
# Specify the correponding supplemental precipitation directories
# that will be searched for input files.
#
# SuppForcing[i]['PcpMandatory']
# Specify whether the Supplemental Precips listed above are mandatory, or optional.
# This is important for layering contingencies if a product is missing,
# but forcing files are still desired.
# False - Not mandatory
# True - Mandatory
#
# SuppForcing[i]['RegridOptPcp']
# Specify regridding options for the supplemental precipitation products.
# 1 -
# 2 -
# 3 -
#
# SuppForcing[i]['PcpTemporalInterp']
# Specify the time interpretation methods for the supplemental precipitation
# products.
# 0 -
# 1 -
# 2 -
#
#SuppForcing[i]['PcpInputOffsets']
# In AnA runs, this value is the offset from the available forecast and 00z
# For example, if forecast are available at 06z and 18z, set this value to 6
#
#SuppForcing[i]['RqiMethod']
# Optional RQI method for radar-based data.
# NONE - Do not use any RQI filtering. Use all radar-based estimates.
# MRMS - Use hourly MRMS Radar Quality Index grids.
# NWM - Use NWM monthly climatology grids (NWM only!!!!)
#
#SuppForcing[i]['RqiThreshold']
# Optional RQI threshold to be used to mask out. Currently used for MRMS products.
# Please choose a value from 0.0-1.0. Associated radar quality index files will be expected
# from MRMS data.
#
#SuppForcing[i]['PcpParamDir']
# Specify an optional directory that contains supplemental precipitation parameter fields,
# I.E monthly RQI climatology
""",
'Ensembles' : 
"""# Ensembles Example
#
# Ensembles:
#  cfsEnsNumber: []
#
# Ensembles['cfsEnsNumber'][i]
# Choose ensemble options for each input forcing file being used. Ensemble options include:
# 1, 2, 3, 4
# Choose the CFS ensemble member number to process"""
}
