'''
Other functionality functions
'''

def fn_building_safety(damage, building_model, damage_consequences, utilities,
                       functionality_options, impeding_temp_repairs):
    '''Check damage that would cause the whole building to be shut down due to
     issues of safety
    
    Parameters
    ----------
    damage: dictionary
     contains per damage state damage, loss, and repair time data for each 
     component in the building
    
    damage_consequences: dictionary
     data structure containing simulated building consequences, such as red
     tags and repair costs ratios
     
    building_model: dictionary
     general attributes of the building model
     
    utilities: dictionary
     data structure containing simulated utility downtimes
     
    functionality_options: dictionary
     recovery time optional inputs such as various damage thresholds
    
    impeding_temp_repairs: dictionary
     contains simulated temporary repairs the impede occuapancy and function
      but are calulated in parallel with the temp repair schedule
    
    Returns
    -------
    recovery_day: dictionary
     simulation of the number of days each fault tree event is affecting building
     safety
     
    comp_breakdowns: dictionary
     simulation of each components contributions to each of the fault tree events 
     
    system_operation_day: dictionary
     simulation of recovery of operation for various systems in the building'''
    
    import numpy as np
    ## Initial Setup
    num_reals = len(damage_consequences['red_tag'])
    num_units = len(damage['tenant_units'])
    num_comps = len(damage['comp_ds_table']['comp_id'])
    
    ## Calculate effect of red tags and fire suppression system
    # Initialize parameters
    recovery_day = {'red_tag' : np.zeros(num_reals), 
                    'shoring' : np.zeros(num_reals), 
                    'hazardous_material' : np.zeros(num_reals), 
                    'fire_suppression' : np.zeros(num_reals)}
    
    # check if building has fire supprsion system
    fs_exists = any(damage['fnc_filters']['fire_building'])
    
 
    # Check damage throughout the building
    comp_breakdowns = {'red_tag' : np.empty([num_reals,num_comps,num_units]),
                       'shoring' : np.empty([num_reals,num_comps,num_units]),
                       'fire_suppression' : np.empty([num_reals,num_comps,num_units])
                       }
    

    for tu in range(num_units):
        # Grab tenant and damage info for this tenant unit
        repair_complete_day = damage['tenant_units'][tu]['recovery']['repair_complete_day'].copy()
        repair_complete_day_w_tmp = damage['tenant_units'][tu]['recovery']['repair_complete_day_w_tmp'].copy()
        
        is_damaged = np.logical_and(np.array(damage['tenant_units'][tu]['qnt_damaged']) > 0, np.array(damage['tenant_units'][tu]['worker_days']) > 0)
        ## Red Tags
        # The day the red tag is resolved is the day when all damage (anywhere in building) that has
        # the potential to cause a red tag is fixed (ie max day)
        if any(damage['fnc_filters']['red_tag']):
            recovery_day['red_tag'] = np.fmax(recovery_day['red_tag'],
                                          np.array(damage_consequences['red_tag'])*np.nanmax(repair_complete_day[:,damage['fnc_filters']['red_tag']], axis=1))
   
        # Component Breakdowns
        
        comp_breakdowns['red_tag'][:,:,tu] = recovery_day['red_tag'].reshape(num_reals,1) * damage_consequences['red_tag_impact']
        
        
        ## Local Shoring
        if np.logical_and(any(damage['fnc_filters']['requires_shoring']), functionality_options['include_local_stability_impact']):
            #Any unresolved damao documentatige (temporary or otherwise) that requires shoring,
            # blocks occupancy to the whole building
            recovery_day['shoring'] = np.fmax(recovery_day['shoring'],
                                      np.nanmax(repair_complete_day_w_tmp[:,damage['fnc_filters']['requires_shoring']], axis=1)) 
        
            # Componet Breakdowns (the time it takes to shore or fully repair each
            # component is the time it blocks occupancy for)
            comp_breakdowns['shoring'][:,:,tu] = damage['fnc_filters']['requires_shoring'] * repair_complete_day_w_tmp * is_damaged

    
    
        ## Day the fire suppression system is operating again (for the whole building)
        if np.logical_not(functionality_options['fire_watch']) and fs_exists:
            # any major damage fails the system for the whole building so take the max
            recovery_day['fire_suppression'] = np.fmax(recovery_day['fire_suppression'], np.amax(repair_complete_day[:,damage['fnc_filters']['fire_building']], axis=1))
    
            # Consider utilities (assume no backup water supply)
            recovery_day['fire_suppression'] = np.fmax(recovery_day['building']['fire'], np.array(utilities['water'])) # Assumes building does not have backup water supply
        
            # Componet Breakdowns
            comp_breakdowns['fire_suppression'][:,:,tu] = damage['fnc_filters']['fire_building'] * repair_complete_day


        ## Hazardous Materials
        # note: hazardous materials are accounted for in building functional
        #assessment here, but are not currently quantified in the component
        # breakdowns
        if any(damage['fnc_filters']['global_hazardous_material']):
            # Any global Nohazardous material shuts down the entire building
            recovery_day['hazardous_material'] = np.fmax(recovery_day['hazardous_material'], np.amax(repair_complete_day[:,damage['fnc_filters']['global_hazardous_material']], axis=1))

    
    ## Building Egress
    '''Calculate when falling hazards or racking of doors affects the building
    safety due to limited entrance and exit door access'''
    
    '''Simulate a random location of the doors on two sides of the building for
    each realization. Location is defined at the center of the door as a
    fraction of the building width on that side
    This is acting a random p value to determine if the unknown location of
    the door is within the falling hazard zone'''
    
    door_location = np.random.rand(num_reals , building_model['num_entry_doors'])
    
    # Assign odd doors to side 1 and even doors to side two
    door_numbers = np.linspace(1,building_model['num_entry_doors'], building_model['num_entry_doors'])
    door_side = np.ones(building_model['num_entry_doors'])
    door_side[np.remainder(door_numbers, 2) == 0] = 2
    door_side = door_side.astype('int')
    
    # Determine the quantity of falling hazard damage and when it will be resolved
    day_repair_fall_haz = np.zeros([num_reals,building_model['num_entry_doors']])
    fall_haz_comps_day_rep = np.zeros([num_reals,num_comps,num_units,building_model['num_entry_doors']])
    comp_affected_lf = np.zeros([num_reals,num_comps,num_units])
    scaffold_filt = damage['comp_ds_table']['resolved_by_scaffolding'].astype(bool)
    
    repair_complete_day_w_tmp = np.empty([num_reals,num_comps,num_units])
    for tu in range(num_units):
        tmp_or_full_complete_day = damage['tenant_units'][tu]['recovery']['repair_complete_day_w_tmp'].copy()

        '''Effect of falling hazards on building safety are resolved either by
        full repair, local temp repair, or erecting scaffolding. Whatever
        occurs first'''
        isdamaged = 1*(np.array(damage['tenant_units'][tu]['qnt_damaged']) > 0).astype('float')
        isdamaged[isdamaged == 0] = np.nan # mark undamaged cases as NaN to help combine factors below
        
        scaffold_day = impeding_temp_repairs['scaffold_day'].reshape(num_reals,1) *  isdamaged[:,scaffold_filt]
        complete_day_w_scaffold = tmp_or_full_complete_day
        complete_day_w_scaffold[:,scaffold_filt] = np.fmin(tmp_or_full_complete_day[:,scaffold_filt], scaffold_day)
        repair_complete_day_w_tmp[:,:,tu] = complete_day_w_scaffold

    # Loop through component repair times to determine the day it stops affecting re-occupancy
    num_repair_time_increments = np.sum(damage['fnc_filters']['ext_fall_haz_all'])*num_units # possible unique number of loop increments
    edge_lengths = np.row_stack((np.array(building_model['edge_lengths']), np.array(building_model['edge_lengths'])))
    
    affected_ratio={}
    for side in range(4):
        affected_ratio['side_'+str(side+1)]=np.zeros([num_reals, num_units]) #FZ# Initiated with zeros. Check later if it works
    for i in range(num_repair_time_increments):
        # Calculate the falling hazards per side
        for tu in range(num_units):
            for side in range(4): # assumes there are 4 sides
                lf_affected_direct_scale_all_comps = damage['comp_ds_table']['exterior_falling_length_factor'] * damage['comp_ds_table']['unit_qty'] * damage['tenant_units'][tu]['qnt_damaged_side_' + str(side+1)]  #FZ# +1 done to account for python indexing starting with 0.       
                lf_affected_sf_all_comps = damage['comp_ds_table']['exterior_falling_length_factor'] * damage['comp_ds_table']['unit_qty'] * damage['tenant_units'][tu]['qnt_damaged_side_' + str(side+1)] / building_model['ht_per_story_ft'][tu]
                
                comp_affected_lf[:,damage['fnc_filters']['ext_fall_haz_lf'],tu] = lf_affected_direct_scale_all_comps[:,damage['fnc_filters']['ext_fall_haz_lf']]
                comp_affected_lf[:,damage['fnc_filters']['ext_fall_haz_sf'],tu] = lf_affected_sf_all_comps[:,damage['fnc_filters']['ext_fall_haz_sf']]
                comp_affected_lf[:,damage['fnc_filters']['ext_fall_haz_ea'],tu] = lf_affected_direct_scale_all_comps[:,damage['fnc_filters']['ext_fall_haz_ea']]    
                
                comp_affected_ft_this_story = comp_affected_lf[:,:,tu].copy()
                affected_ft_this_story = np.fmin(np.sum(comp_affected_ft_this_story,axis = 1), edge_lengths[side,tu]) # Assumes cladding components do not occupy the same perimeter space
                
                affected_ratio['side_'+str(side+1)][:,tu] = np.fmin((affected_ft_this_story)/ edge_lengths[side,tu],1)


        # Calculate the time increment for this loop
        delta_day = np.nanmin(np.nanmin(repair_complete_day_w_tmp[:,damage['fnc_filters']['ext_fall_haz_all'],:],axis =2), axis=1)
        delta_day[np.isnan(delta_day)] = 0
        if sum(delta_day) == 0:
            break # everything has been fixed
        
        
        # Go through each door to determine which is affected by falling
        # hazards
        for d in range(building_model['num_entry_doors']):
            # Combine affected areas of all stories above the first using SRSS
            # HARDCODED ASSUMPTIONS: DOORS ONLY ON TWO SIDES
            fall_haz_zone = np.fmin(np.sqrt(np.sum(affected_ratio['side_'+str(door_side[d])][:,1:num_units]**2, axis=1)),1)
    
            '''Augment the falling hazard zone with the door access zone
            add the door access width to the width of falling hazards to account
            for the width of the door (ie if any part of the door access zone is
            under the falling hazard, its a problem)'''
            door_access_zone = functionality_options['door_access_width_ft'] / building_model['edge_lengths'][door_side[d]-1][0] #FZ# -1 done to account for python indexing starting from zero
            total_fall_haz_zone = fall_haz_zone + 2*door_access_zone # this is approximating the probability the door is within the falling hazard zone
    
            '''Determine if current damage affects occupancy
            if the randonmly simulated door location is with falling hazard zone'''
            affects_door = door_location[:,door_side[d]-1] < total_fall_haz_zone #FZ# -1 done to account for python indexing starting from zero
    
            # Add days in this increment to the tally
            day_repair_fall_haz[:,d] = day_repair_fall_haz[:,d] + affects_door * delta_day
    
            # Add days to components that are affecting occupancy
            # fall_haz_comps_day_rep[:,:,:,d] = fall_haz_comps_day_rep[:,:,:,d] + ((1 * comp_posing_falling_hazard).transpose(2,0,1) * (affects_door * delta_day).reshape(num_reals,1)).transpose(1,2,0) #FZ# Transpose and reshape done to align nd arrays
            fall_haz_comps_day_rep[:,:,:,d] = fall_haz_comps_day_rep[:,:,:,d] + ((comp_affected_lf > 0 * damage['fnc_filters']['ext_fall_haz_all'].reshape(num_comps,1)).transpose(2,0,1) * (affects_door * delta_day).reshape(num_reals,1)).transpose(1,2,0) #FZ# Transpose and reshape done to align nd arrays      
        
        # Change the comps for the next increment
        repair_complete_day_w_tmp = (repair_complete_day_w_tmp.transpose(2,0,1) - delta_day.reshape(num_reals,1)).transpose(1,2,0)
        repair_complete_day_w_tmp[repair_complete_day_w_tmp <= 0] = np.nan

    
    # Determine when racked doors are resolved
    day_repair_racked = np.zeros([num_reals, building_model['num_entry_doors']])
    side_1_count = 0
    side_2_count = 0
    for d in range(building_model['num_entry_doors']):
        if door_side[d] == 1:
            side_1_count = side_1_count + 1
            day_repair_racked[:,d] = impeding_temp_repairs['door_racking_repair_day'] * (np.array(damage_consequences['racked_entry_doors_side_1']) >= side_1_count)
        else:
            side_2_count = side_2_count + 1
            day_repair_racked[:,d] = impeding_temp_repairs['door_racking_repair_day'] * (np.array(damage_consequences['racked_entry_doors_side_2']) >= side_2_count)

    door_access_day = np.fmax(day_repair_racked, day_repair_fall_haz)
    
    '''Find the days until door egress is regained from resolution of both
    falling hazards or door racking'''
    cum_days = np.zeros(num_reals)
    entry_door_access_day = np.zeros(num_reals)
    door_access_day_nan = door_access_day.copy() #FZ# Be cautious! Numpy arrays are mutable
    door_access_day_nan[door_access_day_nan == 0] = np.nan
    num_repair_time_increments = np.array(building_model['num_entry_doors']) # possible unique number of loop increments
    for i in range(num_repair_time_increments):
        num_accessible_doors = np.sum(door_access_day <= cum_days.reshape(num_reals,1), axis=1)
        entry_door_accessible = num_accessible_doors >= max(functionality_options['min_egress_paths'], functionality_options['egress_threshold'] * building_model['num_entry_doors'])
        # Bean counting for this iteration
        delta_day = np.nanmin(door_access_day_nan, axis=1);
        delta_day[np.isnan(delta_day)] = 0
        door_access_day_nan = door_access_day_nan - delta_day.reshape(num_reals,1)
        cum_days = cum_days + delta_day
        
        # Save recovery time increments
        entry_door_access_day = entry_door_access_day + delta_day * np.logical_not(entry_door_accessible)
        
    # Save recovery day values
    recovery_day['entry_door_access'] = entry_door_access_day
  
    # Determine when Exterior Falling Hazards or doors actually contribute to re-occupancy
    recovery_day['falling_hazard'] = np.fmin(recovery_day['entry_door_access'], np.nanmax(day_repair_fall_haz, axis=1))
    recovery_day['entry_door_racking'] = np.fmin(recovery_day['entry_door_access'], np.nanmax(day_repair_racked,axis=1))
    
    # Component Breakdown
    comp_breakdowns['falling_hazard'] = (np.fmin(recovery_day['entry_door_access'], (np.nanmax(fall_haz_comps_day_rep, axis=3)).transpose(2,1,0))).transpose(2,1,0) #FZ# Transpose done to align the nd array fopr operation
    
    
    ## Fire Safety
    if np.logical_not(functionality_options['fire_watch']) and fs_exists:
        comp_breakdowns_local_fire = np.zeros([num_reals,num_comps,num_units])
        fire_safety_day = np.zeros([num_reals,num_units]) # Day the local fire sprinkler system becomes operational
        filt_fs_drop = damage['fnc_filters']['fire_drops']
        filt_fs_branch = damage['fnc_filters']['fire_unit']
        for tu in range(num_units):
            repair_complete_day = damage['tenant_units'][tu]['recovery']['repair_complete_day'].copy()
            repair_complete_day[repair_complete_day == 0] = np.nan # Make sure zero repair days are NaN
            damaged_comps = damage['tenant_units'][tu]['qnt_damaged']
            num_drops = max(np.array(damage['tenant_units'][tu]['num_comps'])* filt_fs_drop) # Assumes drops are all in one performance group
            num_branches = max(np.array(damage['tenant_units'][tu]['num_comps']) * filt_fs_branch) # Assumes branches are all in one performance group
            
            if (num_drops + num_branches) > 0: # If there are any of these components on in this tenant unit
                # Loop through component repair times to determine the day it stops affecting re-occupanc
                num_repair_time_increments = sum(filt_fs_drop | filt_fs_branch) # possible unique number of loop increments
                
                for i in range(num_repair_time_increments):
                    # Calculate the ratio of damaged drops and branches on this story
                    ratio_damaged_drop = np.sum(damaged_comps * filt_fs_drop, axis=1) / num_drops # assumes comps are not simeltaneous
                    ratio_damaged_branch = np.sum(damaged_comps * filt_fs_branch, axis=1) / num_branches # assumes comps are not simeltaneous
    
                    # Determine if fire drops and branches are adequately operating
                    fire_drop_operational = functionality_options['local_fire_damamge_threshold'] >= ratio_damaged_drop
                    fire_branch_operational = functionality_options['local_fire_damamge_threshold'] >= ratio_damaged_branch
                    local_fire_operational = fire_drop_operational & fire_branch_operational
                    
                    # Add days in this increment to the tally
                    delta_day = np.nanmin(repair_complete_day[:,filt_fs_drop], axis=1);
                    delta_day[np.isnan(delta_day)] = 0
                    fire_safety_day[:,tu] = fire_safety_day[:,tu] + np.logical_not(local_fire_operational) * delta_day
    
                    # Add days to components that are affecting occupancy
                    contributing_drops = ((damaged_comps * filt_fs_drop) > 0)  * np.logical_not(fire_drop_operational).reshape(num_reals,1) #count all components that contributed to non operational fire drops
                    contributing_branches = ((damaged_comps * filt_fs_drop) > 0)  * np.logical_not(fire_branch_operational).reshape(num_reals,1) # count all components that contributed to non operational fire drops
                    contributing_comps = np.amax(contributing_drops, contributing_branches)
                    comp_breakdowns_local_fire[:,:,tu] = comp_breakdowns_local_fire[:,:,tu] + contributing_comps * delta_day.reshape(num_reals,1)
    
                    # Change the comps for the next increment
                    repair_complete_day = repair_complete_day - delta_day.reshape(num_reals,1)
                    repair_complete_day[repair_complete_day <= 0] = np.nan
                    fixed_comps_filt = np.isnan(repair_complete_day)
                    np.array(damaged_comps)[fixed_comps_filt] = 0
  
        # Inoperable fire drips on any story shuts down entire building
        fire_safety_day_building = np.nanmax(fire_safety_day, axis=1)
        
        # Combine parts of fire suppression system
        recovery_day['fire_suppression'] = np.fmax(recovery_day['fire_suppression'], fire_safety_day_building)

        comp_breakdowns['fire_suppression'] = np.fmax(comp_breakdowns['fire_suppression'],comp_breakdowns_local_fire)
    
    ## Delay Red Tag recovery by the time it takes to clear the tag
    sim_red_tag_clear_time = np.ceil(np.random.lognormal(np.log(functionality_options['red_tag_clear_time']),
                                                                functionality_options['red_tag_clear_beta'], num_reals))
    recovery_day['red_tag'] = recovery_day['red_tag'] + sim_red_tag_clear_time * damage_consequences['red_tag']
    comp_breakdowns['red_tag'] = comp_breakdowns['red_tag'] + (sim_red_tag_clear_time.reshape(num_reals,1) * (comp_breakdowns['red_tag'] > 0).transpose(2,0,1)).transpose(1,2,0)
    
    return recovery_day, comp_breakdowns


def fn_story_access(damage, building_model, damage_consequences, 
                    functionality_options, impeding_temp_repairs):
    
    '''Check each story for damage that would cause that story to be shut down due to
    issues of access
    
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
     
    functionality_options: dictionary
     recovery time optional inputs such as various damage thresholds
    
    impeding_temp_repairs: dictionary
     contains simulated temporary repairs the impede occuapancy and function
     but are calulated in parallel with the temp repair schedule
    
    Returns
    -------
    recovery_day: dictionary
     simulation of the number of days each fault tree event is affecting access
     in each story
     
    comp_breakdowns: dictionary
     simulation of each components contributions to each of the fault tree events''' 
    
    import numpy as np
    
    ## Initial Setup
    num_reals = len(damage_consequences['red_tag'])
    num_units = len(damage['tenant_units'])
    num_stories = len(damage['tenant_units'])
    num_comps = len(damage['comp_ds_table']['comp_id'])
    
    # Pre-allocate data
    recovery_day={}
    comp_breakdowns={}
    recovery_day['stairs'] = np.zeros([num_reals,num_units])
    recovery_day['stair_doors'] = np.zeros([num_reals,num_units])
    recovery_day['flooding'] = np.zeros([num_reals,num_units])
    recovery_day['horizontal_egress'] = np.zeros([num_reals,num_units])
    comp_breakdowns['stairs'] = np.zeros([num_reals,num_comps,num_units])
    comp_breakdowns['flooding'] = np.zeros([num_reals,num_comps,num_units])
    comp_breakdowns['horizontal_egress'] = np.zeros([num_reals,num_comps,num_units])
    
    
    ## Horizontal Egress - Fire breaks
    if any(damage['fnc_filters']['fire_break']):
        for tu in range(num_stories):
            # Grab tenant and damage info for this tenant unit
            repair_complete_day_w_tmp = damage['tenant_units'][tu]['recovery']['repair_complete_day_w_tmp'].copy()
    
            # Any significant damage to fire breaks in the story impairs the horizontal egress
            recovery_day['horizontal_egress'][:,tu] = np.fmax(recovery_day['horizontal_egress'][:,tu], np.nanmax(repair_complete_day_w_tmp[:, damage['fnc_filters']['fire_break']], axis=1))
    
            # Componet Breakdowns
            comp_breakdowns['horizontal_egress'][:,:,tu] = damage['fnc_filters']['fire_break'].reshape(1,num_comps) * repair_complete_day_w_tmp

     
    ## STORY FLOODING
    for tu in reversed(range(num_stories)): # Go from top to bottom
        is_damaged = np.array(damage['tenant_units'][tu]['qnt_damaged']) > 0
        flooding_this_story = np.any(is_damaged[:,damage['fnc_filters']['causes_flooding']], axis=1); # Any major piping damage causes interior flooding
        flooding_cleanup_day = flooding_this_story * impeding_temp_repairs['flooding_cleanup_day']
    
        # Save clean up time per component causing flooding
        comp_breakdowns['flooding'][:,:,tu] = damage['fnc_filters']['causes_flooding'].reshape(1,num_comps) * is_damaged * flooding_cleanup_day.reshape(num_reals,1)
    
        # This story is not accessible if any story above has flooding
        recovery_day['flooding'][:,tu] = np.nanmax(np.column_stack((flooding_cleanup_day, recovery_day['flooding'][:,(tu+1):num_units])), axis=1)

    # Go through each story and check if there is sufficient story access (stairs and stairdoors)
    ## STAIRS AND STAIRDOORS
    if num_stories == 1: 
        return recovery_day, comp_breakdowns # Re-occupancy of one story buildigns is not affected by stairway access


    # Augment damage filters with door data
    damage['fnc_filters']['stairs'] = np.append(damage['fnc_filters']['stairs'], np.array([False]))
    damage['fnc_filters']['stair_doors'] = np.append(np.zeros(num_comps), 1).astype(dtype=bool)
    
    ## Go through each story and check if there is sufficient story access (stairs and stairdoors)
    # if stairs don't exist on a story, this will assume they are rugged (along with the stair doors)
    for tu in range(num_stories):
        # Augment damage matrix with door data
        racked_stair_doors = np.fmin(np.array(damage_consequences['racked_stair_doors_per_story'])[:,tu], building_model['stairs_per_story'][tu])
        damage['tenant_units'][tu]['qnt_damaged'] = (np.column_stack((np.array(damage['tenant_units'][tu]['qnt_damaged']), racked_stair_doors))).tolist() #FZ# Converted back to alist to keep it consistent with other objects in the dictionary damage['tenant_units'][tu]
        door_repair_day = 1*(racked_stair_doors > 0) * impeding_temp_repairs['door_racking_repair_day']
        damage['tenant_units'][tu]['recovery']['repair_complete_day'] = np.column_stack((damage['tenant_units'][tu]['recovery']['repair_complete_day'], door_repair_day))
    
        # Quantify damaged stairs on this story
        repair_complete_day = damage['tenant_units'][tu]['recovery']['repair_complete_day'].copy()
        damaged_comps = np.array(damage['tenant_units'][tu]['qnt_damaged']).copy()
        
        # Make sure zero repair days are NaN
        repair_complete_day[repair_complete_day == 0] = np.nan
    
        '''Step through each unique component repair time and determine when
        stairs stop affecting story access'''
        stair_access_day = np.zeros(num_reals) # day story becomes accessible from repair of stairs
        stairdoor_access_day = np.zeros(num_reals) # day story becomes accessible from repair of doors
        filt_all = damage['fnc_filters']['stairs'] | damage['fnc_filters']['stair_doors']
        num_repair_time_increments = sum(filt_all) # possible unique number of loop increments
        for i in range(num_repair_time_increments):
            # number of functioning stairs
            num_dam_stairs = np.sum(damaged_comps * damage['fnc_filters']['stairs'], axis=1) # assumes comps are not simeltaneous
            num_racked_doors = np.sum(damaged_comps * damage['fnc_filters']['stair_doors'], axis=1) # assumes comps are not simeltaneous
            functioning_stairs = building_model['stairs_per_story'][tu] - num_dam_stairs
            functioning_stairdoors = building_model['stairs_per_story'][tu] - num_racked_doors
    
            # Required egress with and without operational fire suppression system
            required_stairs = max(functionality_options['min_egress_paths'] ,functionality_options['egress_threshold'] * building_model['stairs_per_story'][tu])
    
            # Determine Stair Access
            sufficient_stair_access = functioning_stairs >= required_stairs

            # Determine Stair Door Acces
            sufficient_stairdoor_access = functioning_stairdoors >= required_stairs
 
            # Add days in this increment to the tally
            delta_day = np.nanmin(repair_complete_day[:,filt_all], axis=1)
            delta_day[np.isnan(delta_day)] = 0
            stair_access_day = stair_access_day + np.logical_not(sufficient_stair_access)* delta_day
            stairdoor_access_day = stairdoor_access_day + np.logical_not(sufficient_stairdoor_access) * delta_day
    
            # Add days to components that are affecting occupancy
            contributing_stairs = ((damaged_comps * damage['fnc_filters']['stairs'] > 0) * np.logical_not(sufficient_stair_access.reshape(len(sufficient_stair_access),1))) # Count any damaged stairs for realization that have loss of story access
            contributing_stairs = np.delete(contributing_stairs, -1, 1) # remove added door column
            comp_breakdowns['stairs'][:,:,tu] = comp_breakdowns['stairs'][:,:,tu] + contributing_stairs * delta_day.reshape(len(delta_day),1)
    
            # Change the comps for the next increment
            repair_complete_day = repair_complete_day - delta_day.reshape(len(delta_day),1)
            repair_complete_day[repair_complete_day <= 0] = np.nan
            fixed_comps_filt = np.isnan(repair_complete_day)
            damaged_comps[fixed_comps_filt] = 0
           
        ## This story is not accessible if this or any story below has insufficient stair egress
        recovery_day['stairs'][:,tu] = np.nanmax(np.column_stack((stair_access_day, recovery_day['stairs'][:,0:(tu)])), axis=1)
        
        # For the third story and above, the story below is not accessible if
        # there is insufficient stair egress at this story
        if tu >= 2:
            recovery_day['stairs'][:,(tu-1)] = np.nanmax(np.column_stack((stair_access_day, recovery_day['stairs'][:,(tu-1)])), axis=1)
    
        # Damage to doors only affects this story
        recovery_day['stair_doors'][:,tu] = stairdoor_access_day
   
    return recovery_day, comp_breakdowns


def fn_tenant_safety( damage, building_model, functionality_options, 
                     tenant_units):
    '''Check each tenant unit for damage that would cause that tenant unit 
    to be shut down due to issues of locay safety
    
    Parameters
    ----------
    damage: dictionary
     contains per damage state damage, loss, and repair time data for each 
     component in the building
     
    building_model: dictionary
     general attributes of the building model
     
    functionality_options: dictionary
     recovery time optional inputs such as various damage thresholds
     
    tenant_units: DataFrame
     attributes of each tenant unit within the building
    
    Returns
    -------
    recovery_day: dictionary
     simulation of the number of days each fault tree event is affecting safety
     in each tenant unit
    
    comp_breakdowns: dictionary
     simulation of each components contributions to each of the fault tree events''' 
    
    import numpy as np
    
    ##Initial Setup
    num_reals, num_comps = np.shape(damage['tenant_units'][0]['qnt_damaged'])
    num_units = len(damage['tenant_units'])
    comp_types_interior_check = np.unique(damage['comp_ds_table']['comp_type_id'][damage['fnc_filters']['int_fall_haz_all']])
    
    recovery_day={}
    recovery_day['exterior'] = np.zeros([num_reals, num_units])
    recovery_day['interior'] = np.zeros([num_reals, num_units])    
    recovery_day['hazardous_material'] = np.zeros([num_reals, num_units])     
    
    comp_breakdowns = {}
    comp_breakdowns['exterior'] = np.empty([num_reals,num_comps,num_units])
    comp_breakdowns['interior'] = np.empty([num_reals,num_comps,num_units])
    
    # go through each tenant unit and quantify the affect that each system has on reoccpauncy
    for tu in range(num_units):
        # Grab tenant and damage info for this tenant unit
        unit={}
        for key in list(tenant_units.keys()):
            unit[key] = tenant_units[key][tu]
        repair_complete_day_w_tmp = tuple(map(tuple,(damage['tenant_units'][tu]['recovery']['repair_complete_day_w_tmp']))) # day each component (and DS) is reparied of this TU
        #FZ# Made tuple to bypass the issue of mutable numpy array
        '''#Exterior Enclosure 
           Calculated the affected perimeter area of exterior components
           (assuming all exterior components have either lf or sf units)'''
        area_affected_all_linear_comps = damage['comp_ds_table']['exterior_surface_area_factor'] * damage['comp_ds_table']['unit_qty'] * building_model['ht_per_story_ft'][tu] * damage['tenant_units'][tu]['qnt_damaged']
        area_affected_all_direct_scale_comps = damage['comp_ds_table']['exterior_surface_area_factor'] * damage['comp_ds_table']['unit_qty'] * damage['tenant_units'][tu]['qnt_damaged']
        
        # construct a matrix of affected areas from the various damaged component types
        comp_affected_area = np.zeros([num_reals,num_comps])
        comp_affected_area[:,damage['fnc_filters']['exterior_safety_lf']] = area_affected_all_linear_comps[:,damage['fnc_filters']['exterior_safety_lf']]
        comp_affected_area[:,damage['fnc_filters']['exterior_safety_sf']] = area_affected_all_direct_scale_comps[:,damage['fnc_filters']['exterior_safety_sf']]
        
        '''Go each possible unique repair time contributing to interior safety check
           Find when enough repairs are complete such that interior damage no
           longer affects tenant safety'''
        comps_day_repaired = repair_complete_day_w_tmp # define as initial repair day considering tmp repairs
        comps_day_repaired = np.array(comps_day_repaired)
        ext_repair_day = np.zeros(num_reals)
        all_comps_day_repaired = np.zeros([num_reals,num_comps])
        num_repair_time_increments = np.sum(damage['fnc_filters']['exterior_safety_all']) # possible unique number of loop increments
        for i in range(num_repair_time_increments):
            
            # Quantify Affected Area
            area_affected = np.sum(comp_affected_area, axis=1) # Assumes cladding components do not occupy the same perimeter area
            percent_area_affected = area_affected / unit['perim_area'] #FZ# Fraction area
    
            # Check if this is sufficent enough to cause as tenant safety issue
            affects_occupancy = percent_area_affected > functionality_options['exterior_safety_threshold']
    
            # Determine step increment based on the component with the shortest repair time
            delta_day = np.nanmin(comps_day_repaired[:,damage['fnc_filters']['exterior_safety_all']], axis=1)
            delta_day[np.isnan(delta_day)] = 0
            
            # Add increment to the tally of days until the interior damage stops affecting occupancy
            ext_repair_day = ext_repair_day + affects_occupancy * delta_day
            
            # Add days to components that are affecting occupancy
            any_area_affected_all_comps = (damage['fnc_filters']['exterior_safety_all'] * comp_affected_area) > 0 # Count any component that contributes to the loss of occupancy regardless of by how much
            all_comps_day_repaired = all_comps_day_repaired + any_area_affected_all_comps * affects_occupancy.reshape(num_reals,1) * delta_day.reshape(num_reals,1)
            
            # Reduce compent damaged for the next increment based on what was repaired in this increment
            comps_day_repaired = comps_day_repaired - delta_day.reshape(num_reals,1)
            comps_day_repaired[comps_day_repaired <= 0] = np.nan
            fixed_comps_filt = np.isnan(comps_day_repaired)
            comp_affected_area[fixed_comps_filt] = 0

        
        # Save exterior recovery day for this tenant unit
        recovery_day['exterior'][:,tu] = ext_repair_day
        comp_breakdowns['exterior'][:,:,tu] = all_comps_day_repaired
        
        ## Interior Falling Hazards
        # Convert all component into affected areas
        area_affected_all_linear_comps = damage['comp_ds_table']['interior_area_factor'] * damage['comp_ds_table']['unit_qty'] * building_model['ht_per_story_ft'][tu] * damage['tenant_units'][tu]['qnt_damaged']
        area_affected_all_direct_scale_comps   = damage['comp_ds_table']['interior_area_factor'] * damage['comp_ds_table']['unit_qty'] * damage['tenant_units'][tu]['qnt_damaged']
        area_affected_all_bay_comps    = damage['comp_ds_table']['interior_area_factor'] * building_model['struct_bay_area_per_story'][tu] * damage['tenant_units'][tu]['qnt_damaged']
        area_affected_all_build_comps  = damage['comp_ds_table']['interior_area_factor'] * sum(building_model['area_per_story_sf']) * damage['tenant_units'][tu]['qnt_damaged']
        
        # Checking damage that affects components in story below
        repair_complete_day_w_tmp_w_instabilities = repair_complete_day_w_tmp
        repair_complete_day_w_tmp_w_instabilities = np.array(repair_complete_day_w_tmp_w_instabilities) #FZ# coverted to array from tuple
        if tu > 0: #FZ# changed to zero to account for python indexing starting from 0.
            area_affected_below = damage['comp_ds_table']['interior_area_factor'] * building_model['struct_bay_area_per_story'][tu-1] * damage['tenant_units'][tu-1]['qnt_damaged']
            area_affected_all_bay_comps[:,damage['fnc_filters']['vert_instabilities']] = np.fmax(area_affected_below[:,damage['fnc_filters']['vert_instabilities']], area_affected_all_bay_comps[:,damage['fnc_filters']['vert_instabilities']])
            repair_time_below = damage['tenant_units'][tu-1]['recovery']['repair_complete_day_w_tmp']
            repair_complete_day_w_tmp_w_instabilities[:,damage['fnc_filters']['vert_instabilities']] = np.fmax(repair_time_below[:,damage['fnc_filters']['vert_instabilities']],np.array(repair_complete_day_w_tmp)[:,damage['fnc_filters']['vert_instabilities']])
        
    
        # construct a matrix of affected areas from the various damaged component types
        comp_affected_area = np.zeros([num_reals,num_comps])
        comp_affected_area[:,damage['fnc_filters']['int_fall_haz_lf']] = area_affected_all_linear_comps[:,damage['fnc_filters']['int_fall_haz_lf']]
        comp_affected_area[:,damage['fnc_filters']['int_fall_haz_sf']] = area_affected_all_direct_scale_comps[:,damage['fnc_filters']['int_fall_haz_sf']]
        comp_affected_area[:,damage['fnc_filters']['int_fall_haz_ea']] = area_affected_all_direct_scale_comps[:,damage['fnc_filters']['int_fall_haz_ea']]        
        comp_affected_area[:,damage['fnc_filters']['int_fall_haz_bay']] = area_affected_all_bay_comps[:,damage['fnc_filters']['int_fall_haz_bay']]
        comp_affected_area[:,damage['fnc_filters']['int_fall_haz_build']] = area_affected_all_build_comps[:,damage['fnc_filters']['int_fall_haz_build']]
        
        '''Go each possible unique repair time contributing to interior safety check
        Find when enough repairs are complete such that interior damage no
        longer affects tenant safety'''
        comps_day_repaired = repair_complete_day_w_tmp_w_instabilities # define as initial repair day considering tmp repairs
        int_repair_day = np.zeros(num_reals)
        all_comps_day_repaired = np.zeros([num_reals,num_comps])
        num_repair_time_increments = np.sum(damage['fnc_filters']['int_fall_haz_all']) # possible unique number of loop increments
        for i in range(num_repair_time_increments):
            # Quantify Affected Area
            diff_comp_areas = np.empty([num_reals, len(comp_types_interior_check)])
            for cmp in range(len(comp_types_interior_check)):
                filt = damage['comp_ds_table']['comp_type_id'] == comp_types_interior_check[cmp] # check to see if it matches the first part of the ID (ie the type of comp)
                diff_comp_areas[:,cmp] = np.sum(comp_affected_area[:,filt], axis=1)
            
            area_affected = np.sqrt(np.sum(diff_comp_areas**2, axis=1)) # total area affected is the srss of the areas in the unit
            
            # Determine if current damage affects occupancy
            percent_area_affected = np.fmin(area_affected / unit['area'], 1)
            affects_occupancy = percent_area_affected > functionality_options['interior_safety_threshold']
            
            # Determine step increment based on the component with the shortest repair time
            delta_day = np.nanmin(comps_day_repaired[:,damage['fnc_filters']['int_fall_haz_all']], axis=1)
            delta_day[np.isnan(delta_day)] = 0
            
            # Add increment to the tally of days until the interior damage
            # stops affecting occupancy
            int_repair_day = int_repair_day + affects_occupancy * delta_day
            
            # Add days to components that are affecting occupancy
            any_area_affected_all_comps = (damage['fnc_filters']['int_fall_haz_all'] * comp_affected_area) > 0 # Count any component that contributes to the loss of occupancy regardless of by how much
            all_comps_day_repaired = all_comps_day_repaired + any_area_affected_all_comps * affects_occupancy.reshape(num_reals,1) * delta_day.reshape(num_reals,1)
            
            # Reduce compent damaged for the next increment based on what was repaired in this increment
            comps_day_repaired = comps_day_repaired - delta_day.reshape(num_reals,1)
            comps_day_repaired[comps_day_repaired <= 0] = np.nan
            fixed_comps_filt = np.isnan(comps_day_repaired)
            comp_affected_area[fixed_comps_filt] = 0
        
        
        # Save interior recovery day for this tenant unit
        recovery_day['interior'][:,tu] = int_repair_day
        comp_breakdowns['interior'][:,:,tu] = all_comps_day_repaired
        
        ''' Hazardous Materials
          note: hazardous materials are accounted for in building functional
          assessment here, but are not currently quantified in the component
          breakdowns'''
        if any(damage['fnc_filters']['local_hazardous_material']):
            # Any local hazardous material shuts down the entire tenant unit
            recovery_day['hazardous_material'][:,tu] = np.nanmax(repair_complete_day_w_tmp[:,damage['fnc_filters']['local_hazardous_material']], axis=1) 
        else:
            recovery_day['hazardous_material'][:,tu] = np.zeros(num_reals)
    
    return recovery_day, comp_breakdowns

    
#########################functional recovery sub functions ########################################

def fn_calc_subsystem_recovery(subsys_filt, damage,
    repair_complete_day, total_num_comps, damaged_comps):
    '''Check whether the components of a particular subsystem have redundancy
    or not and calculate the day the subsystem recovers opertaions
    
    Parameters
    ----------
    subsys_filt: logical array [1 x num_comps_ds]
     indentifies which rows in the damage.comp_ds_info are the components of interest
    
    damage: struct
     contains per damage state damage, loss, and repair time data for each 
     component in the building
    
    repair_complete_day: array [num_reals x num_comps_ds]
     day reapairs are complete for each components damage state for a given
     tenant unit
    
    total_num_comps: array [1 x num_comps_ds]
     total number of each component damage state in this tenant unit
    
    damaged_comps: array [num_reals x num_comps_ds]
     total number of damaged components in each damage state in this tenant unit
    
    Returns
    -------
    subsys_repair_day: array [num reals x 1]
     The day this subsystem stops affecting functoin in a given tenant unit'''


    import numpy as np    
    ## Initial Setup
    num_reals = len(repair_complete_day)
    if len(damage['comp_ds_table']['parallel_operation'][subsys_filt])>0:
        is_redundant = max(damage['comp_ds_table']['parallel_operation'][subsys_filt]) # should all be the same within a subsystem
    else: 
        is_redundant = 0
    any_comps = any(subsys_filt)
    
    ## Check if the componet has redundancy
    if any_comps:
        if is_redundant == 1:
            ## go through each component in this subsystem and find number of damaged units
            comps = np.unique(damage['comp_ds_table']['comp_idx'][subsys_filt])
            num_tot_comps = np.zeros(len(comps))
            num_damaged_comps = np.zeros([num_reals,len(comps)])
            for c in range(len(comps)):
                this_comp = np.logical_and(subsys_filt, damage['comp_ds_table']['comp_idx'] == comps[c])
                num_tot_comps[c] = max(total_num_comps * this_comp) # number of units across all ds should be the same
                num_damaged_comps[:,c] = np.nanmax(damaged_comps * this_comp, axis=1)

    
            ## sum together multiple components in this subsystem
            subsystem_num_comps = sum(num_tot_comps)
            subsystem_num_damaged_comps = np.sum(num_damaged_comps, axis=1);
            ratio_damaged = subsystem_num_damaged_comps / subsystem_num_comps
    
            ## Check failed component against the ratio of components required for system operation
            # system fails when there is an insufficient number of operating components
            n1_redundancy = max(damage['comp_ds_table']['n1_redundancy'][subsys_filt]) # should all be the same within a subsystem
            if subsystem_num_comps == 0: # No components at this level
                subsystem_failure = np.zeros([num_reals,1])
            elif subsystem_num_comps == 1: # Not actually redundant
                subsystem_failure = subsystem_num_damaged_comps == 1;
            elif n1_redundancy ==1:
                # These components are designed to have N+1 redundncy rates,
                # meaning they are designed to lose one component and still operate at
                # normal level
                subsystem_failure = subsystem_num_damaged_comps > 1
            else:
                # Use a predefined ratio
                redundancy_threshold = max(damage['comp_ds_table']['redundancy_threshold'][subsys_filt]) # should all be the same within a subsystem
                subsystem_failure = ratio_damaged > redundancy_threshold
    
            ## Calculate recovery day and combine with other subsystems for this tenant unit
            # assumes all quantities in each subsystem are repaired at
            # once, which is true for our current repair schedule (ie
            # system level at each story)
            subsys_repair_day = np.nanmax(subsystem_failure.reshape(len(subsystem_failure),1) * subsys_filt.reshape(1, len(subsys_filt)) * repair_complete_day, axis=1) 
        
            '''else: This subsystem has no redundancy
                any major damage to the components fails the subsystem at this
                tenant unit'''
        else: 
            subsys_repair_day = np.nanmax(repair_complete_day * subsys_filt.reshape(1, len(subsys_filt)), axis=1)

    else: # No components were populated in this subsystem
        subsys_repair_day = np.zeros(num_reals)

    return subsys_repair_day


def fn_building_level_system_operation( damage, damage_consequences, 
                                        building_model, utilities, 
                                        functionality_options):
    
    '''Calculate the day certain systems recovery building-level opertaions
    
    Parameters
    ----------
    damage: dictionary
      contains per damage state damage, loss, and repair time data for each 
      component in the building
     
    damage_consequences: dictionary
      dictionary containing simulated building consequences, such as red
      tags and repair costs ratios
     
    building_model: dictionary
      general attributes of the building model
    
    utilities: dictionary
      dictionary containing simulated utility downtimes
     
    functionality_options: dictionary
      recovery time optional inputs such as various damage thresholds
    
    Returns
    -------
    system_operation_day['building']: dictionary
      simulation of the day operation is recovered for various systems at the
      building level
     
    system_operation_day['comp']: dictionary
      simulation number of days each component is affecting building system
      operations'''
    
 
    # import packages
    from functionality import other_functionality_functions
    import numpy as np
    
    system_operation_day = {'building' : {}, 'comp' : {}}
    ## Initial Setep
    num_stories = building_model['num_stories']
    num_reals = len(damage_consequences['red_tag'])
    num_comps = len(damage['comp_ds_table']['comp_id'])
    
    system_operation_day['building']['hvac_main'] = np.zeros(num_reals)
    
    system_operation_day['comp']['elev_quant_damaged'] = np.zeros([num_reals,num_comps])
    system_operation_day['comp']['elev_day_repaired'] = np.zeros([num_reals,num_comps])
    system_operation_day['comp']['electrical_main'] = np.zeros([num_reals,num_comps])
    system_operation_day['comp']['water_potable_main'] = np.zeros([num_reals,num_comps])
    system_operation_day['comp']['water_sanitary_main'] = np.zeros([num_reals,num_comps])
    system_operation_day['comp']['elevator_mcs'] = np.zeros([num_reals,num_comps])
    system_operation_day['comp']['data_main'] = np.zeros([num_reals,num_comps])
    
    ## Loop through each story/TU and quantify the building-level performance of each system (e.g. equipment that severs the entire building)
    for tu in range(num_stories):
        damaged_comps = np.array(damage['tenant_units'][tu]['qnt_damaged'])
        initial_damaged = damaged_comps > 0
        total_num_comps = np.array(damage['tenant_units'][tu]['num_comps'])
        repair_complete_day = damage['tenant_units'][tu]['recovery']['repair_complete_day']
        
        ## Elevators
        # Assumed all components affect entire height of shaft
        system_operation_day['comp']['elev_quant_damaged'] = np.fmax(
            system_operation_day['comp']['elev_quant_damaged'], 
            damage['tenant_units'][tu]['qnt_damaged'] * 
            damage['fnc_filters']['elevators'])
        
        system_operation_day['comp']['elev_day_repaired'] = np.fmax(
            system_operation_day['comp']['elev_day_repaired'], 
            repair_complete_day * damage['fnc_filters']['elevators'])
        
        # Motor Control system - Elevators
        system_operation_day['comp']['elevator_mcs'] = np.fmax(
            system_operation_day['comp']['elevator_mcs'], 
            repair_complete_day * damage['fnc_filters']['elevator_mcs'])
        
        ## Electrical
        system_operation_day['comp']['electrical_main'] = np.fmax(
            system_operation_day['comp']['electrical_main'], 
            repair_complete_day * damage['fnc_filters']['electrical_main'])
        

        ## Water
        system_operation_day['comp']['water_potable_main'] = np.fmax(
            system_operation_day['comp']['water_potable_main'], 
            repair_complete_day * damage['fnc_filters']['water_main'])
        
        system_operation_day['comp']['water_sanitary_main'] = np.fmax(
            system_operation_day['comp']['water_sanitary_main'], 
            repair_complete_day * damage['fnc_filters']['sewer_main'])        
        
        
        ## HVAC
        building_hvac_subsystems = list(damage['fnc_filters']['hvac']['building'].keys())
        for s in range(len(building_hvac_subsystems)):
            # Initialize variables
            subsys_label = building_hvac_subsystems[s]

            if ('building' in system_operation_day.keys()) == False or ('building' in system_operation_day.keys() and (subsys_label in system_operation_day['building']) ==  False):
                # Initialize variables if not already initialized
                system_operation_day['building'][subsys_label] = np.zeros(num_reals)
                system_operation_day['comp'][subsys_label] = np.zeros([num_reals,num_comps])
                
            # go through each subsystem and calculate how long entire building
            # operation is impaired
            subs = list(damage['fnc_filters']['hvac']['building'][subsys_label].keys())
                
            for b in range(len(subs)):
                filt = damage['fnc_filters']['hvac']['building'][subsys_label][subs[b]]
                
                repair_day = other_functionality_functions.fn_calc_subsystem_recovery( filt, damage,
                     repair_complete_day, total_num_comps, damaged_comps)
                
                comps_breakdown = filt.reshape(1, num_comps) * initial_damaged * repair_day.reshape(num_reals,1)
                
                # combine with previous stories
                system_operation_day['building'][subsys_label] = np.fmax(system_operation_day['building'][subsys_label], repair_day)
                system_operation_day['comp'][subsys_label] = np.fmax(system_operation_day['comp'][subsys_label], comps_breakdown)
                
        ## Data
        system_operation_day['comp']['data_main'] = np.fmax(system_operation_day['comp']['data_main'], repair_complete_day * damage['fnc_filters']['data_main'])
        
    ## Calculate building level consequences for systems where any major main damage leads to system failure
    system_operation_day['building']['electrical_main'] = np.nanmax(system_operation_day['comp']['electrical_main'], axis=1)  # any major damage to the main equipment fails the system for the entire building
    system_operation_day['building']['water_potable_main'] = np.nanmax(system_operation_day['comp']['water_potable_main'], axis=1)  # any major damage to the main pipes fails the system for the entire building
    system_operation_day['building']['water_sanitary_main'] = np.nanmax(system_operation_day['comp']['water_sanitary_main'], axis=1) # any major damage fails the system for the whole building so take the max
    system_operation_day['building']['elevator_mcs'] = np.nanmax(system_operation_day['comp']['elevator_mcs'], axis=1) # any major damage fails the system for the whole building so take the max
    system_operation_day['building']['data_main'] = np.nanmax(system_operation_day['comp']['data_main'], axis=1)  # any major damage to the main equipment fails the system for the entire building
   
    ## Account for External Utilities impact on system Operation
    # Electricity
    system_operation_day['building']['electrical_main'] = np.fmax(system_operation_day['building']['electrical_main'] , utilities['electrical'])
   
    # Potable water
    system_operation_day['building']['water_potable_main'] = np.fmax(system_operation_day['building']['water_potable_main'], utilities['water'])
    
    # Assume hvac control runs on electricity and heating system runs on gas
    system_operation_day['building']['hvac_control'] = np.fmax(system_operation_day['building']['hvac_control'], system_operation_day['building']['electrical_main'])
    system_operation_day['building']['hvac_heating'] = np.fmax(system_operation_day['building']['hvac_heating'], utilities[functionality_options['heat_utility']])

    return system_operation_day


def fn_tenant_function( damage, building_model, system_operation_day, 
                        subsystems, tenant_units, impeding_temp_repairs, functionality_options):
    
    '''Check each tenant unit for damage that would cause that tenant unit 
    to not be functional
    
    Parameters
    ----------
    damage: dictionary
      contains per damage state damage, loss, and repair time data for each 
      component in the building
    
    building_model: dictionary
      general attributes of the building model
      system_operation_day.building: struct
      simulation of the day operation is recovered for various systems at the
      building level
     
    system_operation_day.comp: dictionary
      simulation number of days each component is affecting building system
      operations
    
    subsystems: DataFrame
      data table containing information about each subsystem's attributes
    
    tenant_units: DataFrame
      attributes of each tenant unit within the building
    
    impeding_temp_repairs: dictionary
      contains simulated temporary repairs the impede occuapancy and function
      but are calulated in parallel with the temp repair schedule
    
    functionality_options: dictionary
      recovery time optional inputs such as various damage thresholds
      
    Returns
    -------
    recovery_day: dictionary
      simulation of the number of days each fault tree event is affecting
      function in each tenant unit
    
    comp_breakdowns: dictionary
      simulation of each components contributions to each of the 
      fault tree events''' 

    import numpy as np
    import sys
    
    '''Subfunction'''
    def subsystem_recovery(subsystem, damage, repair_complete_day, 
                           total_num_comps, damaged_comps, 
                           initial_damaged, dependancy):

        # import packages
        from functionality import other_functionality_functions
        
        # Set variables
        recovery_day_all = dependancy['recovery_day'].copy()
        comp_breakdowns_all = dependancy['comp_breakdown'].copy()
        
        # Go through each component group in this subsystem and determine recovery
        # based on impact of system operation at the tenant unit level
        subs = list(damage['fnc_filters']['hvac']['tenant'][subsystem].keys())
        for b in range(len(subs)):
            filt = damage['fnc_filters']['hvac']['tenant'][subsystem][subs[b]]
            recovery_day = other_functionality_functions.fn_calc_subsystem_recovery(filt, damage, repair_complete_day, total_num_comps, damaged_comps)
            comps_breakdown = filt * initial_damaged * recovery_day.reshape(len(recovery_day),1)
            recovery_day_all = np.fmax(recovery_day_all, recovery_day) # combine with previous stories
            comp_breakdowns_all = np.fmax(comp_breakdowns_all,comps_breakdown)
    
        return recovery_day_all, comp_breakdowns_all
    '''Subfunction ends'''
    
    '''Subfunction'''
    def check_roof_function(roof_sys_filter, damage_threshold, repair_complete_day_w_tmp, qnt_damaged, num_comps):

        # Check the roof area for function (seal and function)
        num_comp_damaged = roof_sys_filter * qnt_damaged
        num_roof_comps = roof_sys_filter * num_comps
        
        comps_day_repaired = np.array(repair_complete_day_w_tmp)
        roof_recovery_day = np.zeros(np.shape(comps_day_repaired)[0])
        all_comps_day_roof = np.zeros(np.shape(comps_day_repaired))
        num_repair_time_increments = sum(roof_sys_filter) # possible unique number of loop increments

        # Loop through each unique repair time increment and determine when stops affecting function
        for i in range(num_repair_time_increments):
            # Determine the area of roof affected 
            percent_area_affected = np.sum(num_comp_damaged, axis = 1) / sum(num_roof_comps) # Assumes roof components do not occupy the same area of roof            
            # Determine if current damage affects function for this tenant unit
            # if the area of exterior wall damage is greater than what is
            # acceptable by the tenant 
            affects_function = percent_area_affected >= damage_threshold

            # Add days in this increment to the tally
            delta_day = np.nanmin(comps_day_repaired[:, roof_sys_filter],axis = 1)
            delta_day[np.isnan(delta_day)] = 0
            roof_recovery_day = roof_recovery_day + affects_function * delta_day

            # Add days to components that are affecting function
            any_area_affected_all_comps = num_comp_damaged > 0 # Count any component that contributes to the loss of function regardless of by how much
            all_comps_day_roof = all_comps_day_roof + any_area_affected_all_comps * (affects_function * delta_day).reshape(len(delta_day),1)

            # Change the comps for the next increment
            # reducing damage for what has been repaired in this time increment
            comps_day_repaired = comps_day_repaired - delta_day.reshape(len(delta_day),1)
            comps_day_repaired[comps_day_repaired <= 0] = np.nan
            fixed_comps_filt = np.isnan(comps_day_repaired)
            num_comp_damaged[fixed_comps_filt] = 0

        return all_comps_day_roof, roof_recovery_day
    '''Subfunction ends'''
    
    ## Initial Setup
    num_units = len(damage['tenant_units'])
    num_reals, num_comps = np.shape(np.array(damage['tenant_units'][0]['qnt_damaged']))
    num_stories = building_model['num_stories']
    
    recovery_day = {
        'elevators' : np.zeros([num_reals,num_units]),
        'exterior' : np.zeros([num_reals,num_units]),
        'roof': np.zeros([num_reals,num_units]),
        'interior' : np.zeros([num_reals,num_units]),
        'electrical' : np.zeros([num_reals,num_units]),
        'flooding' : np.zeros([num_reals,num_units]),
        'water_potable' : np.zeros([num_reals,num_units]),
        'water_sanitary' : np.zeros([num_reals,num_units]),
        'hvac_ventilation' : np.zeros([num_reals,num_units]),     
        'hvac_cooling' : np.zeros([num_reals,num_units]),
        'hvac_heating' : np.zeros([num_reals,num_units]),
        'hvac_exhaust' : np.zeros([num_reals,num_units]),
        'data' : np.zeros([num_reals,num_units]),
        }
    
    comp_breakdowns = {
        'elevators' : np.zeros([num_reals,num_comps,num_units]),
        'electrical' : np.zeros([num_reals,num_comps,num_units]),
        'exterior' : np.zeros([num_reals,num_comps,num_units]),
        'roof' : np.zeros([num_reals,num_comps,num_units]),
        'interior' : np.zeros([num_reals,num_comps,num_units]),
        'flooding' : np.zeros([num_reals,num_comps,num_units]),
        'water_potable' : np.zeros([num_reals,num_comps,num_units]),
        'water_sanitary' : np.zeros([num_reals,num_comps,num_units]),
        'hvac_ventilation' : np.zeros([num_reals,num_comps,num_units]),
        'hvac_cooling' : np.zeros([num_reals,num_comps,num_units]),
        'hvac_heating' : np.zeros([num_reals,num_comps,num_units]),
        'hvac_exhaust' : np.zeros([num_reals,num_comps,num_units]),
        'data' : np.zeros([num_reals,num_comps,num_units]),        
        }
    
    ## Go through each tenant unit, define system level performacne and determine tenant unit recovery time
    ## STORY FLOODING
    for tu in reversed(range(num_stories)): # Go from top to bottom
        is_damaged = np.array(damage['tenant_units'][tu]['qnt_damaged']) > 0
        flooding_this_story = np.any(is_damaged[:,damage['fnc_filters']['causes_flooding']], axis=1) # Any major piping damage causes interior flooding
        flooding_recovery_day = flooding_this_story * impeding_temp_repairs['flooding_repair_day']
    
        # Save clean up time per component causing flooding
        comp_breakdowns['flooding'][:,:,tu] = damage['fnc_filters']['causes_flooding'] * is_damaged * flooding_recovery_day.reshape(num_reals,1)
    
        # This story is not accessible if any story above has flooding
        if tu < num_stories-1: #FZ# If this story id not top story
            recovery_day['flooding'][:,tu] = np.nanmax(np.column_stack((flooding_recovery_day, recovery_day['flooding'][:,(tu+1):num_stories])), axis = 1)
        else: #FZ# If this story is top story
            recovery_day['flooding'][:,tu] = flooding_recovery_day                         
    
    ## SYSTEM SPECIFIC CONSEQUENCES    
    for tu in range(num_units):
        damaged_comps = np.array(damage['tenant_units'][tu]['qnt_damaged'])
        initial_damaged = damaged_comps > 0
        total_num_comps = np.array(damage['tenant_units'][tu]['num_comps'])
        unit={}
        for key in list(tenant_units.keys()):
            unit[key] = tenant_units[key][tu]        
        
        repair_complete_day = tuple(map(tuple,damage['tenant_units'][tu]['recovery']['repair_complete_day'])) #FZ# Made tuple to bypass the issue of mutable numpy array
        repair_complete_day_w_tmp = tuple(map(tuple, damage['tenant_units'][tu]['recovery']['repair_complete_day_w_tmp'])) #FZ# Made tuple to bypass the issue of mutable numpy array
        
        ## Elevators
        if unit['is_elevator_required'] == 1:
            comps_day_repaired= tuple(map(tuple,system_operation_day['comp']['elev_day_repaired'])) #FZ# Made tuple to bypass the issue of mutable numpy array
            comps_day_repaired = np.array(comps_day_repaired)
            comps_day_repaired[comps_day_repaired == 0] = np.nan
            comps_quant_damaged = tuple(map(tuple,system_operation_day['comp']['elev_quant_damaged'])) #FZ# Made tuple to bypass the issue of mutable numpy array
            comps_quant_damaged = np.array(comps_quant_damaged)
            elev_function_recovery_day = np.zeros(num_reals)
            elev_comps_day_fnc = np.zeros([num_reals,num_comps])
            num_repair_time_increments = sum(damage['fnc_filters']['elevators']) # possible unique number of loop increments
            # Loop through each unique repair time increment and determine when
            # stops affecting function
            for i in range(num_repair_time_increments):
                '''Take the max of component damage to determine the number of
                shafts/cabs that are damaged/non_operational
                This assumes that different elevator components are correlated'''
                num_damaged_elevs = np.nanmax(comps_quant_damaged, axis=1) # this assumes elevators are in one performance group if simeltaneous
                num_damaged_elevs = np.fmin(num_damaged_elevs, building_model['num_elevators']) # you can never have more elevators damaged than exist
                
                '''If elevators are in mutliple performance groups and those
                elevators have simultaneous damage states, it is not possible
                to count the number of damaged elevators without additional
                information'''
                num_elev_pgs = len(np.unique(damage['comp_ds_table']['comp_idx'][damage['fnc_filters']['elevators']]))
                is_sim_ds = any(damage['comp_ds_table']['is_sim_ds'][damage['fnc_filters']['elevators']])
                if (num_elev_pgs > 1) and is_sim_ds:
                    sys.exit('Error! PBEE_Recovery:Function','Elevator Function check does not handle multiple performance groups with simultaneous damage states')
                
    
                # quantifty the number of occupancy needing to use the elevators
                # all occupants above the first floor will try to use the elevators
                building_occ_per_elev = sum(building_model['occupants_per_story'][1:len(building_model['occupants_per_story'])]) / (building_model['num_elevators'] - num_damaged_elevs) 
                
                # elevator function check
                # do tenants have sufficient elevator access need based on
                # elevators that are still operational
                # affects_function = building_occ_per_elev > max(unit['occ_per_elev'])
                affects_function = building_occ_per_elev > unit['occ_per_elev'] #FZ# Check. Why max is done . Only a single value per unit
                # Add days in this increment to the tally
                delta_day = np.nanmin(comps_day_repaired[:,damage['fnc_filters']['elevators']], axis=1)
                delta_day[np.isnan(delta_day)] = 0
                elev_function_recovery_day = elev_function_recovery_day + affects_function * delta_day
                
                # Add days to components that are affecting occupancy
                any_elev_damage = comps_quant_damaged > 0 # Count any component that contributes to the loss of function regardless of by how much 
                elev_comps_day_fnc = elev_comps_day_fnc + any_elev_damage * affects_function.reshape(num_reals,1) * delta_day.reshape(num_reals,1)
    
                # Change the comps for the next increment
                comps_day_repaired = comps_day_repaired - delta_day.reshape(num_reals,1)
                comps_day_repaired[comps_day_repaired <= 0] = np.nan
                fixed_comps_filt = np.isnan(comps_day_repaired)
                comps_quant_damaged[fixed_comps_filt] = 0
            
            power_supply_recovery_day = np.fmax(system_operation_day['building']['elevator_mcs'], system_operation_day['building']['electrical_main'])
            
            recovery_day['elevators'][:,tu] = np.fmax(elev_function_recovery_day, power_supply_recovery_day) # electrical system and utility
            power_supply_recovery_day_comp = np.fmax(system_operation_day['comp']['elevator_mcs'], system_operation_day['comp']['electrical_main'])
            comp_breakdowns['elevators'][:,:,tu] = np.fmax(elev_comps_day_fnc, power_supply_recovery_day_comp)
        
        
        ## Exterior Enclosure 
        # Perimeter Cladding (assuming all exterior components have either lf or sf units)
        area_affected_lf_all_comps = damage['comp_ds_table']['exterior_surface_area_factor'] * damage['comp_ds_table']['unit_qty'] * building_model['ht_per_story_ft'][tu] * damage['tenant_units'][tu]['qnt_damaged']
        area_affected_direct_scale_all_comps = damage['comp_ds_table']['exterior_surface_area_factor'] * damage['comp_ds_table']['unit_qty'] * damage['tenant_units'][tu]['qnt_damaged']
       
        comp_affected_area = np.zeros([num_reals,num_comps])
        comp_affected_area[:,damage['fnc_filters']['exterior_seal_lf']] = area_affected_lf_all_comps[:,damage['fnc_filters']['exterior_seal_lf']]
        comp_affected_area[:,damage['fnc_filters']['exterior_seal_sf']] = area_affected_direct_scale_all_comps[:,damage['fnc_filters']['exterior_seal_sf']]
        comp_affected_area[:,damage['fnc_filters']['exterior_seal_ea']] = area_affected_direct_scale_all_comps[:,damage['fnc_filters']['exterior_seal_ea']]
        
        comps_day_repaired = np.array(repair_complete_day)
        ext_function_recovery_day = np.zeros(num_reals)
        all_comps_day_ext = np.zeros([num_reals,num_comps])
        num_repair_time_increments = sum(damage['fnc_filters']['exterior_seal_all']) # possible unique number of loop increments
        # Loop through each unique repair time increment and determine when stops affecting function
        for i in range(num_repair_time_increments):
            # Determine the area of wall which has severe exterior encolusure damage 
            area_affected = np.sum(comp_affected_area, axis=1) # Assumes cladding components do not occupy the same perimeter area
            percent_area_affected = np.fmin(area_affected / unit['perim_area'], 1) # normalize it. #FZ# Should be fraction area?
            
            # Determine if current damage affects function for this tenant unit
            # if the area of exterior wall damage is greater than what is
            # acceptable by the tenant 
            affects_function = percent_area_affected > unit['exterior'] 
            
            # Add days in this increment to the tally
            delta_day = np.nanmin(comps_day_repaired[:,damage['fnc_filters']['exterior_seal_all']], axis=1)
            delta_day[np.isnan(delta_day)] = 0
            ext_function_recovery_day = ext_function_recovery_day + affects_function * delta_day
            # Add days to components that are affecting occupancy
            any_area_affected_all_comps = comp_affected_area > 0 # Count any component that contributes to the loss of occupance regardless of by how much
            all_comps_day_ext = all_comps_day_ext + any_area_affected_all_comps * affects_function.reshape(num_reals,1) * delta_day.reshape(num_reals,1)
            
            # Change the comps for the next increment
            # reducing damage for what has been repaired in this time increment
            comps_day_repaired = comps_day_repaired - delta_day.reshape(num_reals,1)
            comps_day_repaired[comps_day_repaired <= 0] = np.nan
            fixed_comps_filt = np.isnan(comps_day_repaired)
            comp_affected_area[fixed_comps_filt] = 0
            
        recovery_day['exterior'][:,tu] = ext_function_recovery_day
        comp_breakdowns['exterior'][:,:,tu] = all_comps_day_ext        

        if unit['story'] == num_stories: # If this is the top story, check the roof for function
            #Roof structure check
            all_comps_day_roof_struct, roof_structure_recovery_day = check_roof_function(damage['fnc_filters']['roof_structure'],
                                                                                        np.array(subsystems['redundancy_threshold'][subsystems['id'] == 21])[0],
                                                                                        repair_complete_day_w_tmp,
                                                                                        damage['tenant_units'][tu]['qnt_damaged'],
                                                                                        damage['tenant_units'][tu]['num_comps'])
            
            # Roof seatherproofing check
            all_comps_day_roof_weather, roof_weather_recovery_day = check_roof_function(damage['fnc_filters']['roof_weatherproofing'],
                                                                                        np.array(subsystems['redundancy_threshold'][subsystems['id'] == 22])[0],
                                                                                        repair_complete_day_w_tmp,
                                                                                        damage['tenant_units'][tu]['qnt_damaged'],
                                                                                        damage['tenant_units'][tu]['num_comps'])           
           
            # Combine branches
            recovery_day['roof'][:,tu] = np.fmax(roof_structure_recovery_day, roof_weather_recovery_day)
            comp_breakdowns['roof'][:,:,tu] = np.fmax(all_comps_day_roof_struct, all_comps_day_roof_weather)
        
        ## Interior Area
        area_affected_lf_all_comps    = damage['comp_ds_table']['interior_area_factor'] * damage['comp_ds_table']['unit_qty'] * building_model['ht_per_story_ft'][tu] * damage['tenant_units'][tu]['qnt_damaged']
        area_affected_direct_scale_all_comps    = damage['comp_ds_table']['interior_area_factor'] * damage['comp_ds_table']['unit_qty'] * damage['tenant_units'][tu]['qnt_damaged']
        area_affected_bay_all_comps   = damage['comp_ds_table']['interior_area_factor'] * building_model['struct_bay_area_per_story'][tu] * damage['tenant_units'][tu]['qnt_damaged']
        area_affected_build_all_comps = damage['comp_ds_table']['interior_area_factor'] * sum(building_model['area_per_story_sf']) * damage['tenant_units'][tu]['qnt_damaged']
        
        repair_complete_day_w_tmp_w_instabilities = np.array(repair_complete_day_w_tmp)
        if tu > 0: #FZ# changed to 0 to account for python index starting from 0.
            area_affected_below = damage['comp_ds_table']['interior_area_factor'] * building_model['struct_bay_area_per_story'][tu-1] * damage['tenant_units'][tu-1]['qnt_damaged']
            area_affected_bay_all_comps[:,damage['fnc_filters']['vert_instabilities']] = np.fmax(
                area_affected_below[:,damage['fnc_filters']['vert_instabilities']],area_affected_bay_all_comps[:,damage['fnc_filters']['vert_instabilities']])
            repair_time_below = damage['tenant_units'][tu-1]['recovery']['repair_complete_day_w_tmp']
            repair_complete_day_w_tmp_w_instabilities[:,damage['fnc_filters']['vert_instabilities']] = np.fmax(
                repair_time_below[:,damage['fnc_filters']['vert_instabilities']], np.array(repair_complete_day_w_tmp)[:,damage['fnc_filters']['vert_instabilities']])

    
        comp_affected_area = np.zeros([num_reals,num_comps])
        comp_affected_area[:,damage['fnc_filters']['interior_function_lf']] = area_affected_lf_all_comps[:,damage['fnc_filters']['interior_function_lf']]
        comp_affected_area[:,damage['fnc_filters']['interior_function_sf']] = area_affected_direct_scale_all_comps[:,damage['fnc_filters']['interior_function_sf']]
        comp_affected_area[:,damage['fnc_filters']['interior_function_ea']] = area_affected_direct_scale_all_comps[:,damage['fnc_filters']['interior_function_ea']]        
        comp_affected_area[:,damage['fnc_filters']['interior_function_bay']] = area_affected_bay_all_comps[:,damage['fnc_filters']['interior_function_bay']]
        comp_affected_area[:,damage['fnc_filters']['interior_function_build']] = area_affected_build_all_comps[:,damage['fnc_filters']['interior_function_build']]
    
        frag_types_in_check = np.unique(damage['comp_ds_table']['comp_type_id'][damage['fnc_filters']['interior_function_all']])
        comps_day_repaired = repair_complete_day_w_tmp_w_instabilities.copy()
    
        int_function_recovery_day = np.zeros(num_reals)
        int_comps_day_repaired = np.zeros([num_reals,num_comps])
        num_repair_time_increments = sum(damage['fnc_filters']['interior_function_all']) # possible unique number of loop increments
        # Loop through each unique repair time increment and determine when stops affecting function
        for i in range(num_repair_time_increments):
            # Quantify the affected area (based on srss of differenct component
            # types)
            diff_comp_areas = np.empty([num_reals, len(frag_types_in_check)])
            for cmp in range(len(frag_types_in_check)):
                filt = damage['comp_ds_table']['comp_type_id'] == frag_types_in_check[cmp] # check to see if it matches the first part of the ID (ie the type of comp)
                diff_comp_areas[:,cmp] = np.sum(comp_affected_area[:,filt], axis=1)
            
            area_affected = np.sqrt(np.sum(diff_comp_areas**2, axis=1)) # total area affected is the srss of the areas in the unit
            percent_area_affected = np.fmin(area_affected / unit['area'], 1) # no greater than the total unit area
        
            # Determine if current damage affects function for this tenant unit
            # affects function if the area of interior damage is greater than what is
            # acceptable by the tenant 
            affects_function = percent_area_affected > unit['interior'] 
            
            # Add days in this increment to the tally
            delta_day = np.nanmin(comps_day_repaired[:,damage['fnc_filters']['interior_function_all']], axis=1)
            delta_day[np.isnan(delta_day)] = 0
            int_function_recovery_day = int_function_recovery_day + affects_function * delta_day
            
            # Add days to components that are affecting occupancy
            any_area_affected_all_comps = comp_affected_area > 0 # Count any component that contributes to the loss of occupance regardless of by how much
            int_comps_day_repaired = int_comps_day_repaired + any_area_affected_all_comps * affects_function.reshape(num_reals,1) * delta_day.reshape(num_reals,1)
            
            # Change the comps for the next increment
            # reducing damage for what has been repaired in this time increment
            comps_day_repaired = comps_day_repaired - delta_day.reshape(num_reals,1)
            comps_day_repaired[comps_day_repaired <= 0] = np.nan
            fixed_comps_filt = np.isnan(comps_day_repaired)
            comp_affected_area[fixed_comps_filt] = 0
            
        recovery_day['interior'][:,tu] = int_function_recovery_day
        comp_breakdowns['interior'][:,:,tu] = int_comps_day_repaired
        
        # Water and Plumbing System
        # determine effect on funciton at this tenant unit
        # any major damage to the branch pipes (small diameter) failes for this tenant unit
        tenant_sys_recovery_day = np.nanmax(np.array(repair_complete_day) * damage['fnc_filters']['water_unit'], axis=1) 
        recovery_day['water_potable'][:,tu] = np.fmax(system_operation_day['building']['water_potable_main'],tenant_sys_recovery_day)
              
        # distribute effect to the components
        comp_breakdowns['water_potable'][:,:,tu] = np.fmax(system_operation_day['comp']['water_potable_main'], np.array(repair_complete_day) * damage['fnc_filters']['water_unit'])
        
        # In taller buildings, water needs to be pumped to reach upper stories
        #and therefore requires electrical power
        if unit['story'] > functionality_options['water_pressure_max_story']:
            electrical_failure_controls = system_operation_day['building']['electrical_main'] > recovery_day['water_potable'][:,tu]
            recovery_day['water_potable'][:,tu] = np.fmax(recovery_day['water_potable'][:,tu], system_operation_day['building']['electrical_main'])
            comp_breakdowns['water_potable'][:,:,tu] = np.fmax(comp_breakdowns['water_potable'][:,:,tu] * np.logical_not(electrical_failure_controls).reshape(num_reals,1), 
                                                               system_operation_day['comp']['electrical_main'] * electrical_failure_controls.reshape(num_reals,1))
        
        
        ## Sanitary Waste System
        # determine effect on funciton at this tenant unit
        # any major damage to the branch pipes (small diameter) failes for this tenant unit
        tenant_sys_recovery_day = np.nanmax(repair_complete_day * damage['fnc_filters']['sewer_unit'], axis=1) 
        recovery_day['water_sanitary'][:,tu] = np.fmax(system_operation_day['building']['water_sanitary_main'], tenant_sys_recovery_day)
    
        # distribute effect to the components
        comp_breakdowns['water_sanitary'][:,:,tu] = np.fmax(system_operation_day['comp']['water_sanitary_main'], np.array(repair_complete_day) * damage['fnc_filters']['water_unit'])
    
        # Sanitary waste operation at this tenant unit depends on the 
        # operation of the potable water system at this tenant unit
        recovery_day['water_sanitary'][:,tu] = np.fmax(recovery_day['water_sanitary'][:,tu],recovery_day['water_potable'][:,tu])
        comp_breakdowns['water_sanitary'][:,:,tu] = np.fmax(comp_breakdowns['water_sanitary'][:,:,tu], comp_breakdowns['water_potable'][:,:,tu])
  
        ## Electrical Power System
        # Does not consider effect of backup systems
        if unit['is_electrical_required'] == 1:
            # determine effect on funciton at this tenant unit
            # any major damage to the unit level electrical equipment fails for this tenant unit
            tenant_sys_recovery_day = np.nanmax(np.array(repair_complete_day) * damage['fnc_filters']['electrical_unit'], axis=1)
            recovery_day['electrical'][:,tu] =np.fmax(system_operation_day['building']['electrical_main'], tenant_sys_recovery_day)
                      
            # distribute effect to the components
            comp_breakdowns['electrical'][:,:,tu] = np.fmax(system_operation_day['comp']['electrical_main'], np.array(repair_complete_day) * damage['fnc_filters']['electrical_unit'])

        ## HVAC System
        # HVAC: Control System
        recovery_day_hvac_control = system_operation_day['building']['hvac_control'] # Electrical power is counted in here
        comp_breakdowns_hvac_control = system_operation_day['comp']['hvac_control']
        
        dependancy = {}
        # HVAC: Ventilation
        dependancy['recovery_day'] = recovery_day_hvac_control
        dependancy['comp_breakdown'] = comp_breakdowns_hvac_control
        recovery_day['hvac_ventilation'][:,tu], comp_breakdowns['hvac_ventilation'][:,:,tu] = subsystem_recovery('hvac_ventilation',
                                                                         damage, 
                                                                         repair_complete_day,
                                                                         total_num_comps, 
                                                                         damaged_comps, 
                                                                         initial_damaged, 
                                                                         dependancy)                               

        #HVAC: Heating
        dependancy['recovery_day'] = np.fmax(recovery_day['hvac_ventilation'][:,tu], system_operation_day['building']['hvac_heating'])
        dependancy['comp_breakdown'] = np.fmax(comp_breakdowns['hvac_ventilation'][:,:,tu], system_operation_day['comp']['hvac_heating'])
        recovery_day['hvac_heating'][:,tu], comp_breakdowns['hvac_heating'][:,:,tu] = subsystem_recovery('hvac_heating', 
                                                                     damage, 
                                                                     repair_complete_day, 
                                                                     total_num_comps, 
                                                                     damaged_comps, 
                                                                     initial_damaged, 
                                                                     dependancy)
    
        # HVAC: Cooling
        dependancy['recovery_day'] = np.fmax(recovery_day['hvac_ventilation'][:,tu],system_operation_day['building']['hvac_cooling'])
        dependancy['comp_breakdown'] = np.fmax(comp_breakdowns['hvac_ventilation'][:,:,tu], system_operation_day['comp']['hvac_cooling'])
        recovery_day['hvac_cooling'][:,tu], comp_breakdowns['hvac_cooling'][:,:,tu] = subsystem_recovery('hvac_cooling', 
                                                                     damage, 
                                                                     repair_complete_day, 
                                                                     total_num_comps, 
                                                                     damaged_comps, 
                                                                     initial_damaged, 
                                                                     dependancy)
    
        # HVAC: Exhaust
        dependancy['recovery_day'] = recovery_day_hvac_control
        dependancy['comp_breakdown'] = comp_breakdowns_hvac_control
        recovery_day['hvac_exhaust'][:,tu], comp_breakdowns['hvac_exhaust'][:,:,tu] = subsystem_recovery('hvac_exhaust', 
                                                  damage, 
                                                  repair_complete_day, 
                                                  total_num_comps, 
                                                  damaged_comps, 
                                                  initial_damaged, 
                                                  dependancy)    

        ## Data
        if unit['is_data_required'] == 1 and any(damage['fnc_filters']['data_unit'] | damage['fnc_filters']['data_main']):
        # determine effect on funciton at this tenant unit
        # any major damage to the unit level electrical equipment fails for this tenant unit
            tenant_sys_recovery_day = np.nanmax(repair_complete_day * damage['fnc_filters']['data_unit'], axis=1)
            recovery_day['data'][:,tu] = np.fmax(system_operation_day['building']['data_main'], tenant_sys_recovery_day)

            # Consider effect of external power network
                 
            recovery_day['data'] = np.fmax(recovery_day['data'], system_operation_day['building']['electrical_main'].reshape(num_reals,1))
    
            # distribute effect to the components
            comp_breakdowns['data'][:,:,tu] = np.fmax(system_operation_day['comp']['data_main'], np.array(repair_complete_day) * damage['fnc_filters']['data_unit'])

        ## Post process for tenant-specific requirements 
        # Zero out systems that are not required by the tenant
        # Still need to calculate above due to dependancies between options
        if unit['is_water_potable_required'] != 1:
            recovery_day['water_potable'] = np.zeros([num_reals,num_units])
            comp_breakdowns['water_potable'] = np.zeros([num_reals,num_comps,num_units])

        if unit['is_water_sanitary_required'] != 1:
            recovery_day['water_sanitary'] = np.zeros([num_reals,num_units])
            comp_breakdowns['water_sanitary'] = np.zeros([num_reals,num_comps,num_units])

        if unit['is_hvac_ventilation_required'] != 1:
            recovery_day['hvac_ventilation'] = np.zeros([num_reals,num_units])
            comp_breakdowns['hvac_ventilation'] = np.zeros([num_reals,num_comps,num_units])

        if unit['is_hvac_heating_required'] != 1:
            recovery_day['hvac_heating'] = np.zeros([num_reals,num_units])
            comp_breakdowns['hvac_heating'] = np.zeros([num_reals,num_comps,num_units])

        if unit['is_hvac_cooling_required'] != 1:
            recovery_day['hvac_cooling'] = np.zeros([num_reals,num_units])
            comp_breakdowns['hvac_cooling'] = np.zeros([num_reals,num_comps,num_units])

        if unit['is_hvac_exhaust_required'] != 1:
            recovery_day['hvac_exhaust'] = np.zeros([num_reals,num_units])
            comp_breakdowns['hvac_exhaust'] = np.zeros([num_reals,num_comps,num_units])

    return recovery_day, comp_breakdowns    


def fn_combine_comp_breakdown(comp_ds_table, perform_targ_days, comp_names, reoccupancy, functional):
    '''get the combined reoccupancy/functionality effect of components
    
    Parameters
    ----------
    comp_ds_table: table
      contains basic component attributes
    perform_targ_days: array
      recovery time horizons to consider
    comp_names: cell array
      string ids of components to attribte recovery time to
    reoccupancy: array [num reals x num comp_ds]
      realizations of reoccupancy time broken down for each damage state of
      each component
    functional: array [num reals x num comp_ds]
      realizations of functional recovery time broken down for each damage
      state of each component
    
    Returns
    -------
    combined: array
      Probability of recovering within time horizon for each component
      considering both consequenses from reoccupancy and functional recovery'''
    
    import numpy as np
    ## Method
    combined = np.zeros([len(comp_names),len(perform_targ_days)])
    max_reocc_func = np.fmax(reoccupancy, functional)
    for c in range(len(comp_names)):
        comp_filt = comp_ds_table['comp_id'] == comp_names[c] # find damage states associated with this component    
        combined[c,:] = np.mean(np.nanmax(max_reocc_func[:,comp_filt], axis=1).reshape(len(max_reocc_func),1) > np.array(perform_targ_days).reshape(1, len(perform_targ_days)), axis=0)

    return combined


def fn_extract_recovery_metrics( tenant_unit_recovery_day, 
                                 recovery_day, comp_breakdowns, comp_id, 
                                 simulated_replacement_time):
    '''Reformant tenant level recovery outcomes into outcomes at the building level, 
    system level, and compoennt level
    
    Parameters
    ----------
    tenant_unit_recovery_day: array [num_reals x num_tenant_units]
     simulated recovery day of each tenant unit
     
    recovery_day: dictionary
     simulation of the number of days each fault tree event is affecting
     recovery
    comp_breakdowns: dictionary
     simulation of each components contributions to each of the fault tree events 
     
    comp_id: cell array [1 x num comp damage states]
     list of each fragility id associated with the per component damage
     state structure of the damage object. With of array is the same as the
     arrays in the comp_breakdowns structure
     
    simulated_replacement_time: array [num_reals x 1]
     simulated time when the building needs to be replaced, and how long it
     will take (in days). NaN represents no replacement needed (ie
     building will be repaired)
    Returns
    -------
    recovery['tenant_unit']['recovery_day']: array [num_reals x num_tenant_units]
    simulated recovery day of each tenant unit
    
    recovery['building_level']['recovery_day']: array [num_reals x 1]
    simulated recovery day of the building (all tenant units recovered)
    
    recovery['building_level']['initial_percent_affected']: array [num_reals x 1]
    simulated fraction of the building with initial loss of
    reoccupancy/function
    
    recovery['recovery_trajectory']['recovery_day']: array [num_reals x num recovery steps]
    simulated recovery trajectory y-axis
    
    recovery['recovery_trajectory']['percent_recovered']: array [1 x num recovery steps]
    recovery trajectory x-axis
    
    recovery['breakdowns']['system_breakdowns']: array [num fault tree events x target days]
    fraction of realizations affected by various fault tree events beyond
    specific target recovery days
    
    recovery['breakdowns']['component_breakdowns']: array [num components x target days]
    fraction of realizations affected by various components beyond
    specific target recovery days
    
    recovery['breakdowns']['perform_targ_days']: array [0 x target days]
    specific target recovery days
    
    recovery['breakdowns']['system_names']: array [num fault tree events x 1]
    name of each fault tree event
    
    recovery['breakdowns']['comp_names']: array [num components x 1]
    fragility IDs of each component'''
    
    import numpy as np
    
    recovery={'tenant_unit' : {}, 'building_level' : {}, 'recovery_trajectory' : {}, 'breakdowns' : {}, 'partial' : {}}
    
    ## Initial Setup
    num_units = np.size(tenant_unit_recovery_day,1)

    # Define performance targets
    perform_targ_days = [0, 3, 7, 14, 30, 60, 90, 120, 182, 270, 365]
    #FZ# Maximum day for recovery amongs all tenant units and all realizations
    recovery_day_max = max(np.nanmax(tenant_unit_recovery_day, axis=1))

    #FZ# Append perform target days with more milestones if repair time exceeds 1 year  
    if recovery_day_max <= 365:
        perform_targ_days = perform_targ_days # Number of days for each performance target stripe
    if recovery_day_max > 365:
        num_years = (int(np.floor((recovery_day_max)/365)))
        
        # If number of complete years is more than 2
        for yr in range(num_years-1):
            quarters =[1,2,3]
            for qtr in quarters:
                perform_targ_days.append(365*(yr+1) + qtr * 90)
            perform_targ_days.append(365*(yr+2))
        
        # For final incomplete year
        num_quarters = int(np.floor((recovery_day_max - perform_targ_days[-1])/90))
        for qtr in range(num_quarters):
            perform_targ_days.append(perform_targ_days[-1] +  90)
        perform_targ_days.append(recovery_day_max)
        
        
    # Determine replacement cases
    replace_cases = np.logical_not(np.isnan(simulated_replacement_time))
    ''' Post process tenant-level recovery times
      Overwrite NaNs in tenant_unit_day_functional
      Only NaN where never had functional loss, therefore set to zero'''
    tenant_unit_recovery_day[np.isnan(tenant_unit_recovery_day)] = 0
    
    # Overwrite building replacment cases to replacement time
    tenant_unit_recovery_day[replace_cases,:] = np.array(simulated_replacement_time)[replace_cases].reshape(len(np.array(simulated_replacement_time)[replace_cases]),1)* np.ones([1,num_units])   
   
    ## Save building-level outputs to occupancy structure
    # Tenant Unit level outputs
    recovery['tenant_unit']['recovery_day'] = tenant_unit_recovery_day
    
    # Building level outputs
    recovery['building_level']['recovery_day'] = np.nanmax(tenant_unit_recovery_day, axis=1)
    recovery['building_level']['initial_percent_affected'] = np.mean(tenant_unit_recovery_day > 0, axis=1) # percent of building affected, not the percent of realizations
    
    ## Recovery Trajectory -- calcualte from the tenant breakdowns
    recovery['recovery_trajectory']['recovery_day'] = np.sort(np.column_stack((tenant_unit_recovery_day, tenant_unit_recovery_day)), axis=1)
    recovery['recovery_trajectory']['percent_recovered'] = np.sort(np.concatenate((np.arange(num_units), np.arange(1, num_units+1)))/num_units)
    recovery['building_level']['perform_targ_days'] = perform_targ_days
    recovery['building_level']['prob_of_target'] = np.mean(recovery['building_level']['recovery_day'].reshape(len(recovery['building_level']['recovery_day']),1) > np.array(perform_targ_days).reshape(1,len(perform_targ_days)), axis=0)
    
    
    # Save specific breakdowns for red tags
    if 'building_safety' in recovery_day.keys():
        red_tag_day = recovery_day['building_safety']['red_tag']
        red_tag_day[replace_cases] = np.array(simulated_replacement_time)[replace_cases]
        recovery['building_level']['recovery_day_red_tag'] = red_tag_day

    
    ## Recovery Trajectory -- calcualte from the tenant breakdowns
    recovery['recovery_trajectory']['recovery_day'] = np.sort(np.column_stack((tenant_unit_recovery_day, tenant_unit_recovery_day)), axis =1)
    recovery['recovery_trajectory']['percent_recovered'] = np.sort(np.concatenate((np.arange(0, (num_units)), np.arange(1, (num_units+1))))) / num_units

    #partial recovery
    pct_recovered_targets = [0.1, 0.5, 0.75, 0.8, 1]
    
    # order the tennant recovery days so it's easier to see at what time the required numnber of units
    # are required
    ordered_tenant_repair_days = np.sort(tenant_unit_recovery_day, axis = 1)
    
    for i_pct in range(len(pct_recovered_targets)):
        recovery['partial'][i_pct] = {}
        target_recovery_ratio_units = pct_recovered_targets[i_pct]
        recovery['partial'][i_pct]['target_recovery_ratio_units'] = target_recovery_ratio_units
        recovery['partial'][i_pct]['target_recovery_day'] = perform_targ_days;
        recovery['partial'][i_pct]['prob_of_target'] = {}
        for i_targ_day in range(len(perform_targ_days)):
            targ_day = perform_targ_days[i_targ_day]
            # get the percentage of tenant units recovered at the given day
            # pct_recovered_per_real = np.mean(np.sum(tenant_unit_recovery_day <= targ_day, axis=1) / num_units, axis=1);
            pct_recovered_per_real = np.sum(tenant_unit_recovery_day <= targ_day, axis=1) / num_units
            recovery['partial'][i_pct]['prob_of_target'][i_targ_day] = np.mean(pct_recovered_per_real < target_recovery_ratio_units)
           
            # how many units need to be repaired to meet the percent required 
            reqd_units = int(np.ceil(num_units * target_recovery_ratio_units))
            recovery['partial'][i_pct]['reqd_units'] = reqd_units
            recovery['partial'][i_pct]['mean'] = np.mean(ordered_tenant_repair_days[:, reqd_units-1]) #FZ reqd_units - 1 because pytho indexing start from zero.
            recovery['partial'][i_pct]['median'] = np.percentile(ordered_tenant_repair_days[:, reqd_units-1], 50)
            recovery['partial'][i_pct]['fractile_75'] = np.percentile(ordered_tenant_repair_days[:, reqd_units-1], 75)
            recovery['partial'][i_pct]['fractile_90'] = np.percentile(ordered_tenant_repair_days[:, reqd_units-1], 90)



    ## Format and Save Component-level breakdowns
    # Find the day each ds of each component stops affecting recovery for any story
    
    # Combine among all fault tree events
    component_breakdowns_per_story = 0
    fault_tree_events_LV1 = list(comp_breakdowns.keys())
    for i in range(len(fault_tree_events_LV1)):
        fault_tree_events_LV2 = list(comp_breakdowns[fault_tree_events_LV1[i]].keys())
        for j in range(len(fault_tree_events_LV2)):
            component_breakdowns_per_story = np.fmax(component_breakdowns_per_story, 
                                                 comp_breakdowns[fault_tree_events_LV1[i]][fault_tree_events_LV2[j]])

    
    # Combine among all stories
    # aka time each component's DS affects recovery anywhere in the building
    component_breakdowns = np.nanmax(component_breakdowns_per_story,axis=2)
    
    # Ignore repalcement cases
    # component_breakdowns[replace_cases,:] = np.nan #FZ# conveted to nan
    component_breakdowns = np.delete(component_breakdowns, replace_cases, 0)
    ## Format and Save System-level breakdowns
    # Find the day each system stops affecting recovery for any story
    
    # Combine among all fault tree events
    system_breakdowns = {}
    fault_tree_events_LV1 = list(recovery_day.keys())
    for i in range(len(fault_tree_events_LV1)):
        fault_tree_events_LV2 = list(recovery_day[fault_tree_events_LV1[i]].keys())
        for j in range(len(fault_tree_events_LV2)):
            # Combine among all stories or tenant units to represent the events
            # effect anywhere in the building 
            if len(np.shape(recovery_day[fault_tree_events_LV1[i]][fault_tree_events_LV2[j]]))>1:
                building_recovery_day = np.nanmax(recovery_day[fault_tree_events_LV1[i]][fault_tree_events_LV2[j]], axis=1)
            else:
                building_recovery_day = recovery_day[fault_tree_events_LV1[i]][fault_tree_events_LV2[j]].reshape(len(recovery_day[fault_tree_events_LV1[i]][fault_tree_events_LV2[j]]),1)

            # Ignore repalcement cases
            if len(np.shape(building_recovery_day))>1:
                # building_recovery_day[replace_cases,:] = np.nan #FZ# conveted to nan
                building_recovery_day = np.delete(building_recovery_day, replace_cases, 0)
            else:
                # building_recovery_day[replace_cases] = np.nan #FZ# conveted to nan
                building_recovery_day = np.delete(building_recovery_day, replace_cases)
        
            # Save per "system", which typically represents the fault tree level 2
            if fault_tree_events_LV2[j] in system_breakdowns.keys():
                # If this "system" has already been defined in another fault
                # tree branch, combine togeter by taking the max (i.e., max
                # days this system affects recovery anywhere in the building)
                system_breakdowns[fault_tree_events_LV2[j]] =  np.fmax(
                    system_breakdowns[fault_tree_events_LV2[j]],building_recovery_day.reshape(len(building_recovery_day),1))
            else:
                system_breakdowns[fault_tree_events_LV2[j]] = building_recovery_day.reshape(len(building_recovery_day),1)

    
    ## Format breakdowns as performance targets
    system_names = list(system_breakdowns.keys())
    
    # pre-allocating variables
    comps = np.unique(comp_id)
    recovery['breakdowns']['system_breakdowns'] = np.zeros([len(system_names),len(perform_targ_days)])
    recovery['breakdowns']['component_breakdowns'] = np.zeros([len(comps),len(perform_targ_days)])
    
    # Calculate fraction of realization each system affects recovery for each
    # performance target time
    for s in range(len(system_names)):
        recovery['breakdowns']['system_breakdowns'][s,:] = np.mean(system_breakdowns[system_names[s]] > perform_targ_days, axis=0)

    
    # Calculate fraction of realization each component affects recovery for each
    # performance target time
    for c in range(len(comps)):
        comp_filt = comp_id == comps[c] # find damage states associated with this component
        recovery['breakdowns']['component_breakdowns'][c,:] = np.nanmean(np.max(component_breakdowns[:,comp_filt], axis=1).reshape(len(component_breakdowns),1) > perform_targ_days, axis=0)

    # store this so we can properly overalap the reoccupancy and functionality
    recovery['breakdowns']['component_breakdowns_all_reals'] = component_breakdowns
    
    # Save other variables
    recovery['breakdowns']['perform_targ_days'] = perform_targ_days
    recovery['breakdowns']['system_names'] = system_names
    recovery['breakdowns']['comp_names'] = comps
    
    return recovery