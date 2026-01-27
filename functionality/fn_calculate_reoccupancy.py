def fn_calculate_reoccupancy(damage, damage_consequences, utilities, 
                         building_model, functionality_options, 
                         tenant_units, impeding_temp_repairs):
    '''Calcualte the loss and recovery of building re-occupancy 
    based on global building damage, local component damage, and extenernal factors

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
      attributes of building subsystems; data provided in static tables
      directory
    functionality_options: dictionary
      recovery time optional inputs such as various damage thresholds
    tenant_units: DataFrame
      attributes of each tenant unit within the building
    impeding_temp_repairs: dictionary
     contains simulated temporary repairs the impede occuapancy and function
     but are calulated in parallel with the temp repair schedule
    
    Returns
    -------
    reoccupancy: dictionary
     contains data on the recovery of tenant- and building-level reoccupancy, 
     recovery trajectorires, and contributions from systems and components''' 
    
    ## Initial Set Up
    import numpy as np
    # Import packages
    
    from functionality import other_functionality_functions    
        
    ## Stage 1: Quantify the effect that component damage has on the building safety
    recovery_day={}
    comp_breakdowns={}
    
    recovery_day['building_safety'], comp_breakdowns['building_safety'] = other_functionality_functions.fn_building_safety(damage, building_model, 
                                                                                                                    damage_consequences, utilities, functionality_options
                                                                                                                    ,impeding_temp_repairs)
    
    ## Stage 2: Quantify the accessibility of each story in the building
    recovery_day['story_access'], comp_breakdowns['story_access'] = other_functionality_functions.fn_story_access( damage, 
                                                                                    building_model, damage_consequences, 
                                                                                    functionality_options, impeding_temp_repairs)
    
    # Delete added door column to damage ['comps'] and damage[qnt_damaged]
    if len(damage['tenant_units']) !=1: #FZ# Story is accessible on day zero for 1 story building
        for i in range(len(damage['tenant_units'])):
            # damage['tenant_units'][i]['num_comps'].pop(-1) 
            damage['tenant_units'][i]['recovery']['repair_complete_day'] = damage['tenant_units'][i]['recovery']['repair_complete_day'][:,0:len(damage['comp_ds_table']['comp_id'])]
            for j in range(len(damage['tenant_units'][0]['qnt_damaged'])):
                damage['tenant_units'][i]['qnt_damaged'][j].pop(-1)
        
        damage['fnc_filters']['stairs'] = damage['fnc_filters']['stairs'][0:len(damage['comp_ds_table']['comp_id'])]   
        damage['fnc_filters']['stair_doors'] = damage['fnc_filters']['stair_doors'][0:len(damage['comp_ds_table']['comp_id'])]
    
    ## Stage 3: Quantify the effect that component damage has on the safety of each tenant unit
    recovery_day['tenant_safety'], comp_breakdowns['tenant_safety'] = other_functionality_functions.fn_tenant_safety( damage, building_model, functionality_options, tenant_units)
    
    ## Combine Check to determine the day the each tenant unit is reoccupiable
    # Go through each of the building safety checks and combine them to check the day the building is safe (max of all checks)
    fault_tree_events_building_safety = list(recovery_day['building_safety'].keys())
    day_building_safe = recovery_day['building_safety'][fault_tree_events_building_safety[0]]
    for i in range(1, len(fault_tree_events_building_safety)):
        day_building_safe = np.fmax(day_building_safe, recovery_day['building_safety'][fault_tree_events_building_safety[i]])

    # Go through each of the story access checks and combine them to check the day each story is accessible (max of all checks)
    fault_tree_events_story_access = list(recovery_day['story_access'].keys())
    day_story_accessible = recovery_day['story_access'][fault_tree_events_story_access[0]]
    for i in range(1, len(fault_tree_events_story_access)):
        day_story_accessible = np.fmax(day_story_accessible, recovery_day['story_access'][fault_tree_events_story_access[i]])
    
    # Go through each of the tenant unit safety checks and combine them to check the day each tenant unit is safe (max of all checks)
    fault_tree_events_tenant_unit_safe = list(recovery_day['tenant_safety'].keys())
    day_tenant_unit_safe = recovery_day['tenant_safety'][fault_tree_events_tenant_unit_safe[0]]
    for i in range(1, len(fault_tree_events_tenant_unit_safe)):
        day_tenant_unit_safe = np.fmax(day_tenant_unit_safe, recovery_day['tenant_safety'][fault_tree_events_tenant_unit_safe[i]])

    # Combine checks to determine when each tenant unit is re-occupiable
    day_tenant_unit_reoccupiable = np.fmax(np.fmax(day_building_safe.reshape(len(day_building_safe),1), day_story_accessible), day_tenant_unit_safe)
    
    ## Reformat outputs into occupancy data strucutre
    reoccupancy = other_functionality_functions.fn_extract_recovery_metrics(day_tenant_unit_reoccupiable, 
                                              recovery_day, comp_breakdowns, 
                                              damage['comp_ds_table']['comp_id'],
                                              damage_consequences['simulated_replacement_time'])

    return reoccupancy, recovery_day, comp_breakdowns