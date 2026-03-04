
def fn_calculate_functionality(damage, damage_consequences, utilities, 
                               building_model, subsystems, reoccupancy, 
                               functionality_options, tenant_units, impeding_temp_repairs):
    '''Calcualte the loss and recovery of building functionality based on global building
    damage, local component damage, and extenernal factors

    Parameters
    ----------
    damage: dictionary
     contains per damage state damage, loss, and repair time data for each 
     component in the building
    damage_consequences: dictionary
     data structure containing simulated building consequences, such as red
     tags and repair costs ratios
    utilities: dictionary
     data structure containing simulated utility downtimes
    building_model: dictionary
     general attributes of the building model
    subsystems: DataFrame
     data table containing information about each subsystem's attributes
    reoccupancy: dictionary
     contains data on the recovery of tenant- and building-level function, 
     recovery trajectorires, and contributions from systems and components 
    functionality_options: dictionary
     recovery time optional inputs such as various damage thresholds
    tenant_units: DataFrame
     attributes of each tenant unit within the building
    impeding_temp_repairs: dictionary
     contains simulated temporary repairs the impede occuapancy and function
     but are calulated in parallel with the temp repair schedule
    
    Returns
    -------
    functionality: dictionary
     contains data on the recovery of tenant- and building-level function, 
     recovery trajectorires, and contributions from systems and components''' 
    
    import numpy as np
    
    ## Initial Set Up
    # import packages
    from . import other_functionality_functions
    
    ## Define the day each system becomes functionl - Building level
    system_operation_day = other_functionality_functions.fn_building_level_system_operation(damage, 
                                                              damage_consequences,
                                                              building_model, 
                                                              utilities, 
                                                              functionality_options)
    
    ## Define the day each system becomes functionl - Tenant level
    recovery_day = {}
    comp_breakdowns = {}
    recovery_day['tenant_function'], comp_breakdowns['tenant_function'] = other_functionality_functions.fn_tenant_function(damage,
        building_model, system_operation_day, subsystems, tenant_units, impeding_temp_repairs, functionality_options)
    
    ## Combine Checks to determine per unit functionality
    # Each tenant unit is functional only if it is occupiable
    day_tenant_unit_functional = reoccupancy['tenant_unit']['recovery_day']
    
    # Go through each of the tenant function branches and combines checks
    fault_tree_events = list(recovery_day['tenant_function'].keys())
    for i in range(len(fault_tree_events)):
        day_tenant_unit_functional = np.fmax(day_tenant_unit_functional, recovery_day['tenant_function'][fault_tree_events[i]])
    
    ## Reformat outputs into functionality data strucutre
    functional = other_functionality_functions.fn_extract_recovery_metrics(day_tenant_unit_functional,
        recovery_day, comp_breakdowns, damage['comp_ds_table']['comp_id'], 
        damage_consequences['simulated_replacement_time'])
    
    ## get the combined component breakdown between reoccupancy and function
    functional['breakdowns']['component_combined'] = other_functionality_functions.fn_combine_comp_breakdown(damage['comp_ds_table'], 
    functional['breakdowns']['perform_targ_days'], # assumes names are consistent in both objects
    functional['breakdowns']['comp_names'], # assumes names are consistent in both objects
    reoccupancy['breakdowns']['component_breakdowns_all_reals'],
    functional['breakdowns']['component_breakdowns_all_reals'])
    
    return functional, recovery_day, comp_breakdowns

