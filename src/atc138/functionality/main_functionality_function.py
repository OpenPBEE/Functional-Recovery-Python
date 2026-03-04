def main_functionality(damage, building_model, damage_consequences, 
                       utilities, functionality_options, tenant_units, 
                       subsystems, impeding_temp_repairs):
    '''Calculates building re-occupancy and function based on simulations of
    building damage and calculates the recovery times of each recovery state
    based on a given repair schedule
    
    Parameters
    ----------
    damage: dictionary
     contains per damage state damage, loss, and repair time data for each 
     component in the building
    building_model: dictionary
     general attributes of the building model
    damage_consequences: dictionary
     data structure containing simulated building consequences, such as red
     tags and repair costs ratios
    utilities: dictionary
     data structure containing simulated utility downtimes
    functionality_options: dictionary
     recovery time optional inputs such as various damage thresholds
    tenant_units: DataFrame
     attributes of each tenant unit within the building
    subsystems: DataFrame
     attributes of building subsystems; data provided in static tables
     directory
    
    Returns
    -------
    recovery['reoccupancy']: dictionary
     contains data on the recovery of tenant- and building-level reoccupancy, 
     recovery trajectorires, and contributions from systems and components 
    recovery['functional']: dictionary
     contains data on the recovery of tenant- and building-level function, 
     recovery trajectorires, and contributions from systems and components''' 
    
    from . import fn_calculate_reoccupancy
    from . import fn_calculate_functionality
    from . import fn_check_habitability
    ## Calaculate Building Functionality Restoration Curves
    # Downtime including external delays
    recovery = {}
    reoc_meta = {}
    recovery['reoccupancy'], reoc_meta['recovery_day'], reoc_meta['comp_breakdowns'] = fn_calculate_reoccupancy.fn_calculate_reoccupancy(damage, damage_consequences, utilities,
        building_model, functionality_options, tenant_units, impeding_temp_repairs)
    
    func_meta = {}
    recovery['functional'], func_meta['recovery_day'], func_meta['comp_breakdowns'] =  fn_calculate_functionality.fn_calculate_functionality(damage, damage_consequences, utilities,
        building_model, subsystems, recovery['reoccupancy'], functionality_options, tenant_units, impeding_temp_repairs)
    
    # # delete all the extra per-realization data
    del recovery['reoccupancy']['breakdowns']['component_breakdowns_all_reals']
    del recovery['functional']['breakdowns']['component_breakdowns_all_reals']
    
    
    ## Habitability Checks
    # Overwrite reocuppancy with additional checks from the functionality check
    if 'habitability_requirements' in functionality_options.keys():
        recovery['reoccupancy'] = fn_check_habitability.fn_check_habitability(damage, 
                                                        damage_consequences, 
                                                        reoc_meta, func_meta, 
                                                        functionality_options['habitability_requirements'])
 
    return recovery

