def fn_check_habitability( damage, damage_consequences, reoc_meta, func_meta, 
                          habitability_requirements):
    '''Overwrite reocuppancy with additional checks from the functionality check
    
    Parameters
    ----------
    damage: dictionary
      contains per damage state damage, loss, and repair time data for each 
      component in the building
    damage_consequences: dictionary
      data structure containing simulated building consequences, such as red
      tags and repair costs ratios
    reoc_meta: dictionary
      meta data from reoccupancy assessment
    func_meta: dictionary
      meta data from functionality assessment
    habitability_requirements: dictionary
      basic requirements for habitability beyond basic reoccupancy.
    
    Returns
    -------
    reoccupancy: dictionary
      contains data on the recovery of tenant- and building-level reoccupancy, 
      recovery trajectorires, and contributions from systems and components''' 
    
    import numpy as np
    from functionality import other_functionality_functions
    
    num_reals = len(damage_consequences['red_tag'])
    # Functionality checks to adopt onto reoccupancy requirements for
    # habitability:
        # heating, cooling, vent, exhaust, potable water, sanitary, electrical
    recovery_day = reoc_meta['recovery_day']
    comp_breakdowns = reoc_meta['comp_breakdowns']
    habitability_list = list(habitability_requirements.keys())
    # habitability_list = {'electrical', 'water_potable', 'water_sanitary', 'hvac_ventilation', 'hvac_heating', 'hvac_cooling', 'hvac_exhaust'};
    for i in range(len(habitability_list)):
        if habitability_requirements[habitability_list[i]] ==1: # If this system is required for habitability
            recovery_day['habitability'][habitability_list[i]] = func_meta['recovery_day']['tenant_function'][habitability_list[i]]
            comp_breakdowns['habitability'][habitability_list[i]] = func_meta['comp_breakdowns']['tenant_function'][habitability_list[i]]
   
    # Go through each of the tenant function branches and combines checks
    day_tenant_unit_reoccupiable = np.zeros([num_reals,1])
    fault_tree_events_LV1 = list(recovery_day.keys())
    for i in range(len(fault_tree_events_LV1)):
        fault_tree_events_LV2 = list(recovery_day[fault_tree_events_LV1[i]].keys())
        for j in range(len(fault_tree_events_LV2)):
            day_tenant_unit_reoccupiable = np.fmax(day_tenant_unit_reoccupiable, 
                                               recovery_day[fault_tree_events_LV1[i]][fault_tree_events_LV2[j]].reshape(num_reals, int(np.size(recovery_day[fault_tree_events_LV1[i]][fault_tree_events_LV2[j]])/num_reals)))

    
    # Reformat outputs into reoccupancy data strucutre
    reoccupancy = other_functionality_functions.fn_extract_recovery_metrics(day_tenant_unit_reoccupiable, 
                                              recovery_day, comp_breakdowns, 
                                              damage['comp_ds_table']['comp_id'],
                                              damage_consequences['simulated_replacement_time'])
    
    return reoccupancy

