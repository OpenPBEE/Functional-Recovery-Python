
"""
Other repair schedule functions called by the main repair schedule function
"""
import numpy as np

def fn_allocate_workers_stories(total_worker_days, required_workers_per_story, 
                                average_crew_size, max_crews_building, 
                                max_workers_per_building):

    '''For a given building system, allocate crews to each story to
    determine the system level repair time on each story; not considering
    impeding factors or construction constraints with other systems.
      
      
    Parameters
    ----------
    total_worker_days: [num reals x num stories]
      The total worker days needed to repair damage each story for this
      sequence
      
    required_workers_per_story: array [num reals x num stories]
      Number of workers required to repair damage in each story
      
    average_crew_size: array [num reals x num stories]
      Average crew size required to repair damage in each story
      
    max_crews_building: logical array [num reals x 1]
      maximum number of crews allowed in the building for this system
      
    max_workers_per_building: int
      maximum number of workers allowed in the buildings at a given time
      
    Returns
    -------
    repair_start_day: array [num reals x num stories]
      The number of days from the start of repair of this system until the repair of this system 
      starts on each story
      
    repair_complete_day: array [num reals x num stories]
      The number of days from the start of repair of this system until each story is
      repaired for damage in this system
      
    max_workers_per_story: array [num reals x num stories]
      number of workers required for the repair of this story and system as
      
    Notes
    -----'''
    import sys
    
    ## Initial Setup
    num_reals, num_stories = np.shape(total_worker_days)
    repair_complete_day = np.zeros([num_reals,num_stories])
    repair_start_day = np.empty([num_reals,num_stories])
    repair_start_day[:] = np.nan
    max_workers_per_story = np.zeros([num_reals,num_stories])
    
    ## Allocate workers to each story
    # Loop through iterations of time reduce damage on each story based on assigned workers
    iter = 0;
    while sum(sum(total_worker_days)) > 0.01:
        iter = iter + 1; 
        if iter > 1000: # keep the while loop pandemic contained
            # error('PBEE_Recovery:RepairSchedule', 'Could not converge worker allocations for among stories in sequence');
            sys.exit('Error! could not converge worker allocations for among stories in sequence')
    
        # Determine the available workers in the building
        available_workers_in_building = max_workers_per_building * np.ones([num_reals])
        assigned_workers_per_story = np.zeros([num_reals,num_stories])
        assigned_crews_per_story = np.zeros([num_reals,num_stories]) 
    
        # Define where needs repair
        needs_repair = total_worker_days > 0
    
        # Defined Required Workers
        required_workers_per_story = needs_repair * required_workers_per_story.copy()
        
        '''Assign Workers to each story -- assumes that we wont drop the number
        of crews in order to meet worker per sqft limitations, and instead
        wait until more workers are made available'''
        
        for s in range(num_stories):
            # Are there enough workers to assign a crew
            sufficient_workers = required_workers_per_story[:,s] <= available_workers_in_building
            
            # Assign Workers to this story
            assigned_workers_per_story[sufficient_workers,s] = required_workers_per_story[sufficient_workers,s]
            assigned_crews_per_story[:,s] = assigned_workers_per_story[:,s] / average_crew_size[:,s]
            assigned_crews_per_story[np.isnan(assigned_crews_per_story)] = 0
            num_crews_in_building = np.sum(assigned_crews_per_story, axis=1)
            exceeded_max_crews = num_crews_in_building > max_crews_building
            assigned_workers_per_story[exceeded_max_crews,s] = 0 # don't assign workers if we have exceeded the number of crews allowed in the building
            
            # Define Available Workers
            available_workers_in_building = available_workers_in_building - assigned_workers_per_story[:,s]  
        
        
        # Define the start of repairs for each story
        start_repair_filt = np.isnan(repair_start_day) & (assigned_workers_per_story > 0)
        
        max_day_completed_so_far = np.transpose(np.multiply(np.amax(repair_complete_day, axis=1), np.ones([num_stories,num_reals]))) #FZ# transpose done to align the arrays for operation
         
        repair_start_day[start_repair_filt] =  max_day_completed_so_far[start_repair_filt]
        
        # Calculate the time associated with this increment of the while loop
        in_progress = assigned_workers_per_story > 0 # stories where work is being done
        total_repair_days = np.empty(np.shape(in_progress)) 
        total_repair_days[:] = np.inf # pre-allocate with inf's becuase we take a min later
        total_repair_days[in_progress] = total_worker_days[in_progress] / assigned_workers_per_story[in_progress]
        delta_days = np.amin(total_repair_days,axis=1) # time increment is whatever in-progress story that finishes first 
        delta_days[np.isinf(delta_days)] = 0 # Replace infs from real that has no repair with zero       
        delta_worker_days = np.transpose(np.multiply(np.transpose(assigned_workers_per_story), delta_days)) # time increment is whatever in-progress story that finishes first #FZ# transpose done fto align the arrays for operation
        total_worker_days[in_progress] = np.maximum(total_worker_days[in_progress] - delta_worker_days[in_progress], 0)
        indx_neg_remaining = total_worker_days < 0.001 # find instances of remaining time that are excessively small and don't represent realistic amount of work
        total_worker_days[indx_neg_remaining] = 0  # zero remaining work that is negligible as defined above
        
        # Define Start and Stop of Repair for each story in each sequence
        repair_complete_day = repair_complete_day + np.transpose(np.multiply(delta_days, np.transpose(1*needs_repair))) #FZ# transpose done fto align the arrays for operation
         
        # Max Crew Size for use in later function
        max_workers_per_story = np.maximum(max_workers_per_story , assigned_workers_per_story)
    
    return repair_start_day, repair_complete_day, max_workers_per_story
    

def fn_calc_system_repair_time(damage, repair_type, systems, max_workers_per_building, max_workers_per_story):
    ''' From Dustin's work
    Determine the repair time for each system if repaired in isolation 
      
       Parameters
       ----------
       damage: dictionary
         contains per damage state damage and loss data for each component in the building
       
       repair_type: string
         String identifier indicating whether the repair are temporary or full
  
       systems: DataFrame
         data table containing information about each system's attributes
         
       max_workers_per_building: int
         maximum number of workers allowed in the building at once
         
       max_workers_per_story: array [1 x num_stories]
         maximum number of workers allowed in each story at once
      
       Returns
       -------
       schedule['per_system'][sys]['repair_start_day'] [num reals x num stories]
         The number of days from the start of repair of a specifc system until
         the start of repair of each story for that given system (i.e. the day 
         of the start of repairs relative the to start of this system ... e.g.
         story 1 should always be zero)
         
       schedule['per_system'][sys]['repair_complete_day'] [num reals x num stories]
         The number of days from the start of repair of a specifc system until
         each story is fully repaired for that given system.
         
       schedule['per_system'][sys]['max_num_workers_per_story'] [num reals x num stories]
         The number of workers required to repair each story of this system
         
       schedule['system_totals']['repair_days'] [num reals x num systems]
         The number of days required to repair each system in isolation
         
       schedule['system_totals']['num_workers'] [num reals x num systems]
         The number of workers required for the repair of each system
      
       Notes
       -----'''
       
    def fn_repair_sequence_parameters(damage, repair_type, sys, num_du_per_crew, 
                                      max_crews_per_comp_type, 
                                      max_workers_per_story, 
                                      max_workers_per_building):
        
        '''Define crew sizes, workers, and repair times for each story of a given
        system. Based on worker limiations, and component worker days data from
        the FEMA P-58 assessment.'''
        
        # Define Repair Type Variables (variable within the damage object)
        if repair_type == 'full':
            repair_time_var = 'worker_days'
            system_var = 'system'
            crew_size_var = 'crew_size'
        elif repair_type == 'temp':
            repair_time_var = 'tmp_worker_day'
            system_var = 'tmp_repair_class'
            crew_size_var = 'tmp_crew_size'
        else:
            sys.exit('error!. Unexpected Repair Type')


        # Define Initial Parameters
        num_stories = len(damage['tenant_units']) 
        num_reals, num_comps = np.size(damage['tenant_units'][0]['worker_days'],0), np.size(damage['tenant_units'][0][repair_time_var],1)
        sequence_filt = np.array(damage['comp_ds_table'][system_var]) == sys # identifies which ds indices are in this seqeunce.
        comp_types = np.unique(np.array(damage['comp_ds_table']['comp_idx'])[sequence_filt]) # Types of components in this system
        
        # Pre-allocate variables
        total_worker_days = np.zeros([num_reals,num_stories])
        is_damaged_building = np.zeros([num_reals,num_comps], dtype=bool)
        num_damaged_comp_types = np.zeros([num_reals,num_stories])
        num_damaged_units = np.zeros([num_reals,num_stories])
        average_crew_size = np.zeros([num_reals,num_stories])
        
        for s in range(num_stories):
            # Define damage properties of this system at this story
            num_damaged_units[:,s] = np.sum((1*sequence_filt) * damage['tenant_units'][s]['qnt_damaged'], axis=1) #FZ# Total number of damaged components of one system in one story
            is_damaged = np.logical_and(np.array(damage['tenant_units'][s]['qnt_damaged']) > 0, np.array(damage['tenant_units'][s][repair_time_var]) > 0) #FZ# No
            is_damaged_building = is_damaged_building | is_damaged              #FZ# compiling for all stories. if there is damage at any story, building is damaged
            
            for c in range(len(comp_types)):
                num_damaged_comp_types[:,s] = num_damaged_comp_types[:,s] + np.any((1* np.array(damage['comp_ds_table']['comp_idx']) == comp_types[c]) * (1*is_damaged), axis=1) #FZ# number of types of components damaged in a story in each realization
            
        
            # Calculate total worker days per story per sequences
            total_worker_days[:,s] = np.sum(np.array(damage['tenant_units'][s][repair_time_var])[:,sequence_filt], axis=1) # perhaps consider doing when we first set up this damage data structure
            
            # Determine the required crew size needed for  these repairs
            repair_time_per_comp = np.array(damage['tenant_units'][s][repair_time_var]) / np.array(damage['comp_ds_table'][crew_size_var])
            average_crew_size[:,s] = total_worker_days[:,s] / np.sum(repair_time_per_comp[:,sequence_filt], axis=1)
        
            
        # Define the number of crews needed based on the extent of damage
        num_crews = np.ceil(num_damaged_units / num_du_per_crew)
        num_crews = np.fmin(num_crews, max_crews_per_comp_type * num_damaged_comp_types)
        num_crews = np.fmin(num_crews, np.ceil(num_damaged_units)) # Safety check: num crews should never be greater than the number of damaged components
        
        # Round up total worker days to the nearest day to speed up the worker 
        # allocation loop and implicitly consider change of trade delays
        total_worker_days = np.ceil(total_worker_days)
        
        # Round crew sizes such that we have a realistic size (still implicitly
        # averaged based on type of damage)
        average_crew_size[np.isnan(average_crew_size)] = 0
        average_crew_size = np.round(average_crew_size)
        
        # Limit the number of crews based on the space limitations at this story
        # and the assumed crew size
        worker_upper_lim = np.fmin(max_workers_per_story , max_workers_per_building)
        max_num_crews_per_story = np.fmax(np.floor(worker_upper_lim / average_crew_size), 1)
        num_crews = np.fmin(num_crews, max_num_crews_per_story) 
        
        # Calculate the total number of workers per story for this system
        num_workers = average_crew_size* num_crews
        
        # Repeat calc of number of uniquely damaged component types for the whole building
        num_damaged_comp_types = np.zeros([num_reals])
        
        for c in range(len(comp_types)):
            num_damaged_comp_types = num_damaged_comp_types + np.any( (1* np.array(damage['comp_ds_table']['comp_idx']) == comp_types[c]) * (1*is_damaged_building), axis=1)                                                
                                                                   
        max_crews_building = max_crews_per_comp_type * num_damaged_comp_types
            
        return total_worker_days, num_workers, average_crew_size, max_crews_building
    
    # General Variable
    num_reals = len(damage['tenant_units'][0]['worker_days'])
    schedule = {'system_totals' : {'repair_days' : np.zeros([num_reals,len(systems)])}}
    schedule['system_totals']['num_workers'] = np.zeros([num_reals,len(systems)])
    
    ## Allocate workers to each story for each system
    # Repair finish times assumes all sequences start on day zero
    schedule['per_system']={}    
    for syst in range(len(systems)):
        schedule['per_system'][syst]={}
        # Define the Crew workers and total workers days for this sequence
        # in arrays of [num reals by num stories]
        total_worker_days, num_workers, average_crew_size, max_crews_building = fn_repair_sequence_parameters(damage, repair_type,
            systems['id'][syst], 
            systems['num_du_per_crew'][syst],
            systems['max_crews_per_comp_type'][syst],
            max_workers_per_story,
            max_workers_per_building
        )
        # Allocate workers to each story and determine the total days until
        # repair is complete for each story and sequence

        # other_repair_schedule_functions.
        AA,BB,CC = fn_allocate_workers_stories(total_worker_days, num_workers, 
                                      average_crew_size, max_crews_building, 
                                      max_workers_per_building)

        schedule['per_system'][syst]['repair_start_day']=AA
        schedule['per_system'][syst]['repair_complete_day']=BB
        schedule['per_system'][syst]['max_num_workers_per_story']=CC
    
        # How many days does it take to complete each system in isloation
        schedule['system_totals']['repair_days'][:,syst] = np.amax(schedule['per_system'][syst]['repair_complete_day'], axis=1)
        schedule['system_totals']['num_workers'][:,syst] = np.amax(schedule['per_system'][syst]['max_num_workers_per_story'], axis=1)
        
    return schedule


def fn_prioritize_systems( systems, repair_type, damage, tmp_repair_complete_day, impeding_factors):
    '''Determine the priority of worker allocation for each system and realization
    based on default table priorities, whether they have the potential to 
    affect function and whether they are resolved by temporary repairs.
       
    Parameters
    ----------
    systems: DataFrame
      data table containing information about each system's attributes
    
    repair_type: string
      String identifier indicating whether the repair are temporary or full
      
    damage: dictionary
      contains per damage state damage and loss data for each component in the building
      
    tmp_repair_complete_day: array [num_reals x num_comp]
      contains the day (after the earthquake) the temporary repair time is 
      resolved per damage state damage and realization. Inf represents that
      there is not temporary repair time available for a given components
      damage.
    
    iimpeding_factors: dictionary
      simulated impedance times   
    Returns
    -------
    sys_idx_priority_matrix: index array [num reals x num systems]
      row index to filter system matrices to be prioritized for each
      realiztion. Priority is left to right.
    
    Notes
    ------
    The checks done here are only able to implicitly check for which systems
    affect funtion the most (this prioritizes which have the potential to
    affect function). To explicitly check which systems have the biggest
    impact on function and prioritize those, this check would need to be
    coupled with the function assessment'''
    
    import sys
    
    ## Initial Setup
    # Define Repair Type Variables (variable within the damage object)
    if repair_type == 'full':
        system_var = 'system'
    elif repair_type == 'temp':
        system_var = 'tmp_repair_class'
    else:
        sys.exit('error!. Unexpected Repair Type')


    # initialize variables
    num_sys = len(systems)
    num_reals = np.size(damage['tenant_units'][0]['qnt_damaged'],0)    
    
    # Find which components potentially affect reoccupancy accross any tenant unit
    affects_reoccupancy = np.zeros([num_reals, len(damage['comp_ds_table']['comp_id'])], dtype=bool)
    for s in range(len(damage['tenant_units'])):
        affects_reoccupancy = np.logical_or(affects_reoccupancy, np.logical_and(damage['fnc_filters']['affects_reoccupancy'], np.array(damage['tenant_units'][s]['qnt_damaged']) > 0))

    
    # Find which components potentially affect function accross any tenant unit 
    for s in range(len(damage['tenant_units'])):
        # affects_function = zeros(num_reals, len(damagecomp_ds_table));
        affects_function = np.zeros([num_reals, len(damage['comp_ds_table']['comp_id'])], dtype=bool)
        affects_function = np.logical_or(affects_function, np.logical_and(damage['fnc_filters']['affects_function'], np.array(damage['tenant_units'][s]['qnt_damaged']) > 0))

       
    ## Define ranks for each system 
    sys_affects_reoccupancy = np.zeros([num_reals, num_sys]) # only prioritize the systems that potentially affect reoccupancy
    sys_affects_function = np.zeros([num_reals, num_sys]) # only prioritize the systems that potentially affect function
    sys_tmp_repaired = np.zeros([num_reals, num_sys]) # dont prioitize the systems that are completely resolved by temporary repairs
    
    for syst in range(num_sys):
        sys_filter = damage['comp_ds_table'][system_var] == syst+1 #FZ# +1 done to account for python indexing starting from 0
        if any(sys_filter): # Only if this system is present
            sys_affects_reoccupancy[:,syst] = np.any(affects_reoccupancy[:,sys_filter], axis = 1); # any damage that potentially affects function in this system    
            sys_affects_function[:,syst] = np.any(affects_function[:,sys_filter], axis = 1); # any damage that potentially affects function in this system
            # check if the list (array) is non-empty
            if list(tmp_repair_complete_day): # Only if temp repair data is passed in
                all_sys_tmp_repaired = np.all(np.logical_or(tmp_repair_complete_day[:,sys_filter] < np.inf, np.isnan(tmp_repair_complete_day[:,sys_filter])), axis=1) # is every single damaged component resolved by temp repairs
                tmp_repair_quick = np.nanmax(tmp_repair_complete_day[:,sys_filter], axis=1) < impeding_factors['time_sys'][:,syst] # Are the temp repairs for this system resolved before impeding factors are complete
                sys_tmp_repaired[:,syst] = np.logical_and(all_sys_tmp_repaired, tmp_repair_quick) # damage is quickly resolved by temp repair

    prioritize_system_reoccupancy = np.logical_and(sys_affects_reoccupancy == 1, sys_tmp_repaired == 0)
    prioritize_system_function_only = np.logical_and(sys_affects_function == 1, np.logical_and(prioritize_system_reoccupancy, sys_tmp_repaired == 0))
    non_priorities = np.logical_and(np.logical_not(prioritize_system_reoccupancy), np.logical_not(prioritize_system_function_only))
    
    '''First prioritize reoccpancy repairs (100 classifies first priority bank, 
    important for sort function below), then priotize repairs that only 
    affect function (200 classifies second priority bank). 
    Finally, repair the systems that dont affect reoccupancy or 
    function (300 classifies third priority bank)'''
    
    sys_priority_matrix = prioritize_system_reoccupancy * (100 + np.array(systems['priority'])) + prioritize_system_function_only * (200 + np.array(systems['priority'])) + non_priorities * (300 + np.array(systems['priority']))

    
    # use rank matrix to get row indices of priorities
    sys_idx_priority_matrix = np.argsort(sys_priority_matrix, axis=1)
    
    return sys_idx_priority_matrix


def fn_set_repair_constraints(systems, repair_type, conditionTag):
    '''Define a constraint matrix to be used by repair schedule
    
    Develops a matrix of various constriants between each system (i.e. what
    systems need to be repaired before others) for each realization
    
    Parameters
    ----------
    systems: DataFrame
     data table containing information about each system's attributes

    repair_type: string
      String identifier indicating whether the repair are temporary or full
      
    conditionTag: logical array (num_reals x 1)
     Is the building red tagged for each realization
    
    Returns
    -------
    sys_constraint_matrix: array [num reals x num_sys]
     array of system ids which define which systems (column index) are delayed by the
     system ids (array values)
    
    Notes
    -----
    Shortcoming: as implemented, each system can only be constrained by one
                  other system
    Example:
    [0 0 1 0 0 0 0 6 0]
    Interiors (column 3) are blocked by struture (value of 1 in the 3rd column)
    HVAC (column 8) is blocked by plumbing (value of 6 in the 8th column)'''
    
    import sys
    #Initial Setup
    num_sys = len(systems)
    num_reals = len(conditionTag)
    sys_constraint_matrix = np.zeros([num_reals, num_sys])
    
    # Interior Constraints
    if repair_type == 'full':
        # Interiors are delayed by structural repairs
        interiors_idx = np.where(np.array(systems['name']) == 'interior')[0] #FZ# [0] is done to convert tuple to np array
        structure_idx = np.where(np.array(systems['name']) == 'structural')[0]
 
        sys_constraint_matrix[:,interiors_idx] = structure_idx+1 #FZ# +1 is done to replace with the system id which starts with 1, but python indexing starts at 0. 
        
        # Red Tag Constraints
        # All systems blocked by structural when red tagged
        for rt in np.where(conditionTag)[0]:
            for st in np.where(np.array(systems['name']) != 'structural')[0]:
                sys_constraint_matrix[rt, st] = structure_idx+1
    
    elif repair_type == 'temp':
        shoring_id = 5
        shoring_filt = systems['id'] == shoring_id
        if np.any(shoring_filt): # If shoring is considred as a temp repair measure
            shoring_idx = np.where(shoring_filt)[0][0]
            sys_constraint_matrix[:,np.logical_not(shoring_filt)] = shoring_idx + 1 # all classes that are not shoring idx are blocked by the shoring idx. #FZ# +1 is done to replace with the system id which starts with 1, but python indexing starts at 0. 

    else:
        sys.exit('error. Unexpected Repair Type')
    
    return sys_constraint_matrix


def fn_allocate_workers_systems(systems, sys_repair_days, sys_crew_size, 
                                max_workers_per_building, 
                                sys_idx_priority_matrix, 
                                sys_constraint_matrix, 
                                condition_tag, 
                                sys_impeding_factors):


    '''Stager repair to each system and allocate workers based on the repair
    constraints, priorities, and repair times of each system
    
    Parameters
    ----------
    system_repair_days: [num reals x num systems]
     Number of days from the start of repair of each to the completion of
     the system (assuming all sequences start on day zero)
     
    system_repair_days: [num reals x num systems]
     Number of days from the start of repair of each to the completion of
     the system (assuming all sequences start on day zero)
    
    sys_crew_size: array [num reals x num systems]
     required crew size for each system
     
    max_workers_per_building: int
     Maximum number of workers that can work in the building at the same time 
     
    sys_idx_priority_matrix: matrix [num reals x systems]
     worker allocation order of system id's prioritized for each realiztion
     
    sys_constraint_matrix: array [num reals x num_sys]
     array of system ids which define which systems (column index) are delayed by the
     system ids (array values)
     
    condition_tag: logical array [num reals x 1]
     true/false if the building is red tagged
     
    sys_impeding_factors: array [num_reals x num_sys]
     maximum impedance time (days) for each system. Pass in empty array when
     calculating repair times (i.e. not including impeding factors).
    
    Returns
    -------
    repair_complete_day_per_system: matrix [num reals x num systems]
     Number of days from the start of each sequence to the completion of the
     sequence considering the allocation of workers to each sequence (ie
     some sequences start before others)
     
    worker_data['total_workers']: array [num reals x varies]
     total number of workers in the building at each time step of the worker
     allocation algorthim. The number of columns varies with the number of
     increments of the worker allocation algorithm.
     
    worker_data['day_vector']: array [num reals x varies]
     Day of each time step of the worker allocation algorthim. The number of 
     columns varies with the number of increments of the worker allocation algorithm.
    
    Notes
    -----'''
    
    import sys
    
    def fitler_matrix_by_rows( values, filter_by):
    # Use a identiry matrix to filter values from another matrix by rows
    
        '''Parameters
        ----------
        values: matrix [n x m]
          values to filter by row
        filter: matrix [n x m]
          array indexes to grab from each row of values
        
        Returns
        -------
        filtered_values: matrix [n x m]
          values filtered by rows'''
        
        # Method
        x2t = np.transpose(values)
        idx1 = np.transpose(filter_by)
        y4 = np.zeros(np.shape(idx1))
        for r in range(np.size(values,0)):
            y4[:, r] = x2t[idx1[:, r], r]
        filtered_values = np.transpose(y4)
 
        return filtered_values

    
    ## Initial Setup
    # Initialize Variables
    num_reals, num_sys = np.shape(sys_repair_days)
    priority_system_complete_day = np.zeros([num_reals,num_sys])
    day_vector = np.zeros([num_reals,0])
    total_workers = np.zeros([num_reals,0])
    
    # Re-order system variables based on priority
    priority_sys_workers_matrix = fitler_matrix_by_rows(sys_crew_size, sys_idx_priority_matrix)
    priority_sys_constraint_matrix = fitler_matrix_by_rows(sys_constraint_matrix, sys_idx_priority_matrix)
    priority_sys_repair_days = fitler_matrix_by_rows(sys_repair_days, sys_idx_priority_matrix)
    if sys_impeding_factors.size == 0:
        priority_sys_impeding_factors = np.zeros([num_reals, num_sys])
    else:
        priority_sys_impeding_factors = fitler_matrix_by_rows(sys_impeding_factors, sys_idx_priority_matrix)

    
    # Round up days to the nearest day
    # Provides an implicit change of trade delay, as well as help to reduce the
    # number of delta increments in the following while loop
    priority_sys_repair_days = np.ceil(priority_sys_repair_days)
    priority_sys_impeding_factors = np.ceil(priority_sys_impeding_factors) #FZ# Already rounded. Check requirement
    
    ## Assign workers to each system based on repair constraints
    iter = 0
    current_day = np.zeros(num_reals)
    priority_sys_waiting_days = priority_sys_impeding_factors.copy()
    while sum(sum(priority_sys_repair_days)) > 0.01:
        iter = iter + 1; 
        if iter > 1000: # keep the while loop pandemic contained
            sys.exit('error (PBEE_Recovery:RepairSchedule, Could not converge worker allocations for among systems')

        
        # zero out assigned workers matrix
        assigned_workers = np.zeros([num_reals,num_sys])
        
        # limit available workers to the max that can be on any one given story
        # this ensures next system cannot start until completely unblocked on
        # every story. Need to update for taller buildings which could start
        # next sequence on lower story once previous sequence was far enough
        # along
        available_workers = max_workers_per_building * np.ones(num_reals)
        
        # Define what systems are waiting to begin repairs
        sys_blocked = np.zeros([num_reals,num_sys]).astype(bool)
        sys_incomplete = priority_sys_repair_days > 0
        for s in range(num_sys): # Loop over each system that may constrain something
            constrained_systems = priority_sys_constraint_matrix == s+1 # These systems are constrained by looped system #FZ# s+1 is done to correlate with +1 done in deriving constraint matrix
            constraining_sys_filt = sys_idx_priority_matrix == s; # location in matrix of this system
            is_constraining_sys_incomplete = np.amax(sys_incomplete * constraining_sys_filt, axis=1) # Vec of relizations for looped system
            sys_blocked = sys_blocked | np.transpose(np.transpose(constrained_systems) * is_constraining_sys_incomplete) # System is constrained if blocked by an incomplete system. #FZ# transpose done to align arrays for the operation
        
        # Need to wait for impeding factors or other repairs to finish
        is_waiting = np.transpose(current_day < np.transpose(priority_sys_impeding_factors)) | sys_blocked # assuming impeding factors are the only constraints. #FZ# transpose done to align arrays for the operation
        
        # Define where needs repair
        # System needs repair if there are still repairs days left and it is
        # not waiting to be unblocked
        needs_repair = (priority_sys_repair_days>0) & np.logical_not(is_waiting)
    
        # Defined Required Workers
        required_workers = needs_repair * priority_sys_workers_matrix
        
        # Assign Workers to each system
        for s in range(num_sys):
            # Assign Workers to this systems
            enough_workers = required_workers[:,s] <= available_workers
            assigned_workers[enough_workers,s] = np.fmin(required_workers[enough_workers,s], available_workers[enough_workers])
    
            # Define Available Workers
            # when in series limit available workers to the workers in this system 
            # (occurs for structural systems when the building is red tagged
            is_structural = systems['name'][s] == 'structural'
            in_series = np.logical_and(condition_tag, is_structural)
            available_workers[np.logical_and(in_series, assigned_workers[:,s] > 0)] = 0 #FZ# Python index 0 is structural system
            # when not in series, calc the remaining workers
            available_workers[np.logical_not(in_series)] = available_workers[np.logical_not(in_series)] - assigned_workers[np.logical_not(in_series),s]

        
        # Calculate the time associated with this increment of the while loop
        in_progress = assigned_workers > 0 # sequences where work is being done
        total_repair_days = np.empty(np.shape(in_progress)) # pre-allocate with inf's becuase we take a min later
        total_repair_days[:] = np.inf
        total_repair_days[in_progress] = priority_sys_repair_days[in_progress]
        total_waiting_days = priority_sys_waiting_days.copy()   #FZ# Check is.copy() worke here
        
        total_waiting_days[total_waiting_days == 0] = np.inf # Convert zeros to inf such that zeros are not included in the min in the next step
        
        total_time = np.fmin(total_repair_days,total_waiting_days) # combime repair time and waiting time
        delta_days = np.amin(total_time,axis=1) # time increment is whatever in-progress story that finishes first
        delta_days[np.isinf(delta_days)] = 0 # Replace infs from real that has no repair with zero
                 
        # Reduce waiting time
        priority_sys_waiting_days = np.maximum(np.transpose(np.transpose(priority_sys_waiting_days) - delta_days), 0) #FZ# transpose done to align arrays for the operation
        
        # Reduce time needed for repairs
        delta_days_in_progress = np.transpose(delta_days * np.transpose(in_progress)) # change in repair time for all sequences being worked on #FZ# transpose done to align arrays for the operation
        priority_sys_repair_days[in_progress] = np.maximum(priority_sys_repair_days[in_progress] - delta_days_in_progress[in_progress], 0)
        
        # Define Start and Stop of Repair for each sequence
        priority_system_complete_day = priority_system_complete_day + np.transpose(delta_days * np.transpose(needs_repair | is_waiting)) #FZ# transpose done to align arrays for the operation
        
        # Define Cummulative day of repair
        day_vector = np.column_stack((day_vector, current_day))
        current_day = current_day + delta_days
        
        # Save worker data data over time
        # total_workers = [total_workers, np.sum(assigned_workers,axis=1), np.sum(assigned_workers,axis=1)] #FZ# why assigned workers stored twice - Review
        total_workers = np.column_stack((total_workers, np.sum(assigned_workers,axis=1), np.sum(assigned_workers,axis=1)))
        day_vector = np.column_stack((day_vector, current_day))

        
    # Untangle system_complete_day back into system table order
    
    sys_idx_untangle_matrix = np.argsort(sys_idx_priority_matrix, axis=1)
    
    repair_complete_day_per_system = fitler_matrix_by_rows(priority_system_complete_day, sys_idx_untangle_matrix)
    
    # Save worker data matrices
    worker_data ={'total_workers' : total_workers, 'day_vector' : day_vector}

    return repair_complete_day_per_system, worker_data 


def fn_restructure_repair_schedule( damage, system_schedule,
    repair_complete_day_per_system, systems, repair_type, simulated_red_tags):
    
    '''Redistribute repair schedule data from the system and story level to the component level for use 
    in the functionality assessment (ie, put repair schedule data into the
    damage object)
    
    Parameters
    ----------
    damage: dictionary
     contains per damage state damage and loss data for each component in the building
     
    system_schedule: dictionary
     repair time data for each system in isolation
     
    repair_complete_day_per_system: matrix [num reals x num systems]
     Number of days from the start of each sequence to the completion of the
     sequence considering the allocation of workers to each sequence (ie
     some sequences start before others)
     
    systems: DataFrame
     data table containing information about each system's attributes
    
    repair_type: string
      String identifier indicating whether the repair are temporary or full
      
    simulated_red_tags: logical array [num_reals x 1]
      indicates the realizations that have a red tag
    
    Returns
    -------
    damage: dictionary
     contains per damage state damage and loss data for each component in
     the building, including repair schedule data.
    
    % Notes
    -----
    In the repair start day outputs:
       - Zero = Starts immediately
       - NaN = Repairs never started (because not damaged, has no temp repair, or controlled by red tag)
    In the repair complete day outputs:
       - NaN = No damage (or controlled by red tag)
       - Inf = Is damaged, but has no System/RepairClass assignment (or no temp repair)'''
    
    import sys
    
    ## Initialize Parameters
    num_sys = len(systems)
    num_units = len(damage['tenant_units'])
    
    # Define Repair Type Variables (variable within the damage object)
    if repair_type == 'full':
        repair_time_var = 'worker_days'
        system_var = 'system'
    elif repair_type == 'temp':
        repair_time_var = 'tmp_worker_day'
        system_var = 'tmp_repair_class'
    else:
        sys.exit('Unexpected Repair Type')

    # Initialize recovery field
    damage_recovery = {}
    for tu in range(num_units):
        # Set to inf as a null repair time (will remain inf for components with
        # no attributed system) - matters for temp repairs, shouldnt matter for
        # full repair
        damage_recovery[tu]={}
        damage_recovery[tu]['repair_start_day'] = np.empty(np.shape(np.array(damage['tenant_units'][tu]['qnt_damaged'])))
        damage_recovery[tu]['repair_start_day'][:] = np.nan
        damage_recovery[tu]['repair_complete_day'] = np.empty(np.shape(np.array(damage['tenant_units'][tu]['qnt_damaged'])))
        damage_recovery[tu]['repair_complete_day'][:] = np.inf
        
        # if not damaged, set repair complete time to NaN
        is_damaged = np.logical_and(np.array(damage['tenant_units'][tu]['qnt_damaged']) > 0, np.array(damage['tenant_units'][tu][repair_time_var]) > 0)
        damage_recovery[tu]['repair_complete_day'][np.logical_not(is_damaged)] = np.nan


   ## Redistribute repair schedule data
    for syst in range(num_sys):
        # Calculate system repair times on each story
        system_duration = np.nanmax(system_schedule['per_system'][syst]['repair_complete_day'], axis=1) # total repair time spent in this system over all stories
        start_day = repair_complete_day_per_system[:,syst] - system_duration
        story_start_day = start_day.reshape(len(start_day),1) + system_schedule['per_system'][syst]['repair_start_day']
        story_complete_day = start_day.reshape(len(start_day),1) + system_schedule['per_system'][syst]['repair_complete_day']
        
        # Do not perform temporary repairs when building is red tagged
        if np.logical_and(repair_type == 'temp', np.any(simulated_red_tags)):
            story_start_day[simulated_red_tags.astype(bool),:] = np.nan
            story_complete_day[simulated_red_tags.astype(bool),:] = np.nan
   
        # Re-distribute to each tenant unit
        sys_filt = damage['comp_ds_table'][system_var] == systems['id'][syst] # identifies which ds idices are in this seqeunce  
        for tu in range(num_units):
            is_damaged = np.logical_and(np.array(damage['tenant_units'][tu]['qnt_damaged'])[:,sys_filt] > 0, np.array(damage['tenant_units'][tu][repair_time_var])[:,sys_filt] > 0)
            is_damaged = (is_damaged * 1).astype(float)
            is_damaged[is_damaged == 0] = np.nan
    
            # Re-distribute repair days to component damage states
            damage_recovery[tu]['repair_start_day'][:,sys_filt] = is_damaged* story_start_day[:,tu].reshape(len(story_start_day[:,tu]),1)
            damage_recovery[tu]['repair_complete_day'][:,sys_filt] = is_damaged * story_complete_day[:,tu].reshape(len(story_complete_day[:,tu]),1)
            
    return damage_recovery


def fn_format_gantt_chart_data( damage, systems, simulated_replacement_time):
    '''Reformat data from the damage structure into data that is used for the
    gantt charts
    
    Parameters
    ----------
    damage: dictionary
     contains per damage state damage and loss data for each component in the building
    
    systems: DataFrame
     data table containing information about each system's attributes
    
    simulated_replacement_time: array [num_reals x 1]
     simulated time when the building needs to be replaced, and how long it
     will take (in days). NaN represents no replacement needed (ie
     building will be repaired)
    
Returns
    -------
    repair_schedule: dictionary
     Contians reformated repair schedule data for gantt chart plots for
     both repair time and downtime calculations. Data is reformanted to
     show breakdowns by component, by story, by system, by story within each
     system, and by system within each story.
    
    Notes
    -----
    Since this all has to do with plotting gantt charts, a form of this
    (whether the damage structure or a higher level repair schedule
    structure) should be output and this reformatting logic moved outside the
    functional recovery assessment and into the data visuallation logic'''
    
    ## Initial Setup
    num_stories = len(damage['tenant_units'])
    num_reals = np.size(damage['tenant_units'][0]['recovery']['repair_start_day'],0)
    comps = np.unique(damage['comp_ds_table']['comp_id'])
       
    # Determine replacement cases
    replace_cases = np.logical_not(np.isnan(simulated_replacement_time))

    ## Reformat repair schedule data into various breakdowns
    # Per component
    repair_schedule = {'repair_start_day' : {}, 'repair_complete_day' : {}, 'component_names':[]}
    repair_schedule['repair_start_day']['per_component'] = np.empty([num_reals, len(comps)])
    repair_schedule['repair_start_day']['per_component'][:] = np.nan
    repair_schedule['repair_complete_day']['per_component'] = np.zeros([num_reals,len(comps)])
    for c in range(len(comps)):
        comps_filt = damage['comp_ds_table']['comp_id'] == comps[c]
        for s in range(num_stories):
            repair_schedule['repair_start_day']['per_component'][:,c] = np.nanmin(np.column_stack((repair_schedule['repair_start_day']['per_component'][:,c], damage['tenant_units'][s]['recovery']['repair_start_day'][:,comps_filt])), axis=1)
            repair_schedule['repair_complete_day']['per_component'][:,c] = np.nanmax(np.column_stack((repair_schedule['repair_complete_day']['per_component'][:,c], damage['tenant_units'][s]['recovery']['repair_complete_day'][:,comps_filt])), axis=1)

        repair_schedule['component_names'].append(str(comps[c]))

    
    # Per Story
    repair_schedule['repair_start_day']['per_story'] = np.empty([num_reals, num_stories])
    repair_schedule['repair_start_day']['per_story'][:] = np.nan
    repair_schedule['repair_complete_day']['per_story'] = np.zeros([num_reals,num_stories])
    for s in range(num_stories):
        repair_schedule['repair_start_day']['per_story'][:,s] = np.nanmin(np.column_stack((repair_schedule['repair_start_day']['per_story'][:,s], damage['tenant_units'][s]['recovery']['repair_start_day'])), axis=1)
        repair_schedule['repair_complete_day']['per_story'][:,s] = np.nanmax(np.column_stack((repair_schedule['repair_complete_day']['per_story'][:,s], damage['tenant_units'][s]['recovery']['repair_complete_day'])), axis=1)
    
    
    # Per Repair System
    repair_schedule['repair_start_day']['per_system'] = np.empty([num_reals, len(systems)])
    repair_schedule['repair_start_day']['per_system'][:] = np.nan
    repair_schedule['repair_complete_day']['per_system'] = np.zeros([num_reals,len(systems)])
    for sys in range(len(systems)):
        sys_filt = damage['comp_ds_table']['system'] == systems['id'][sys] # identifies which ds idices are in this seqeunce  
        for s in range(num_stories):
            repair_schedule['repair_start_day']['per_system'][:,sys] = np.nanmin(np.column_stack((repair_schedule['repair_start_day']['per_system'][:,sys], damage['tenant_units'][s]['recovery']['repair_start_day'][:,sys_filt])), axis=1)
            repair_schedule['repair_complete_day']['per_system'][:,sys] = np.nanmax(np.column_stack((repair_schedule['repair_complete_day']['per_system'][:,sys], damage['tenant_units'][s]['recovery']['repair_complete_day'][:,sys_filt])), axis=1)


    repair_schedule['system_names'] = np.array(systems['name'])
    
    # Per system per story
    num_sys_stories = num_stories * len(systems)
    repair_schedule['repair_start_day']['per_system_story'] = np.empty([num_reals,num_sys_stories])
    repair_schedule['repair_start_day']['per_system_story'][:] = np.nan
    repair_schedule['repair_complete_day']['per_system_story'] = np.zeros([num_reals,num_sys_stories])
    id = -1; #FZ# -1 done to account for python indexing starting from 0
    for s in range(num_stories):
        for sys in range(len(systems)):
            id += 1
            sys_filt = damage['comp_ds_table']['system'] == systems['id'][sys] # identifies which ds idices are in this seqeunce  
            repair_schedule['repair_start_day']['per_system_story'][:,id] = np.nanmin(np.column_stack((repair_schedule['repair_start_day']['per_system_story'][:,id], damage['tenant_units'][s]['recovery']['repair_start_day'][:,sys_filt])), axis=1)
            repair_schedule['repair_complete_day']['per_system_story'][:,id] = np.nanmax(np.column_stack((repair_schedule['repair_complete_day']['per_system_story'][:,id], damage['tenant_units'][s]['recovery']['repair_complete_day'][:,sys_filt])), axis=1)

    
    # Per story per system
    num_sys_stories = num_stories * len(systems)
    repair_schedule['repair_start_day']['per_story_system'] = np.empty([num_reals,num_sys_stories])
    repair_schedule['repair_start_day']['per_story_system'][:] = np.nan
    repair_schedule['repair_complete_day']['per_story_system'] = np.zeros([num_reals,num_sys_stories])
    
    id = -1; #FZ# -1 done to account for python indexing starting from 0
    for sys in range(len(systems)):
        for s in range(num_stories):
            id += 1
            sys_filt = damage['comp_ds_table']['system'] == systems['id'][sys] # identifies which ds idices are in this seqeunce 
            repair_schedule['repair_start_day']['per_story_system'][:,id] = np.nanmin(np.column_stack((repair_schedule['repair_start_day']['per_story_system'][:,id], damage['tenant_units'][s]['recovery']['repair_start_day'][:,sys_filt])), axis=1)
            repair_schedule['repair_complete_day']['per_story_system'][:,id] = np.nanmax(np.column_stack((repair_schedule['repair_complete_day']['per_story_system'][:,id], damage['tenant_units'][s]['recovery']['repair_complete_day'][:,sys_filt])), axis=1)
    
    # Overwrite realization for demo and replace cases
    formats = list(repair_schedule['repair_start_day'].keys())
    for f in range(len(formats)):
        repair_schedule['repair_start_day'][formats[f]][replace_cases,:] = 0
        
        format_width = np.size(repair_schedule['repair_complete_day'][formats[f]], 1) # apply replacement time to all comps / systems / stories / etc
        repair_schedule['repair_complete_day'][formats[f]][replace_cases,:] = np.array(simulated_replacement_time)[replace_cases].reshape(len(np.array(simulated_replacement_time)[replace_cases]),1) * np.ones([1,format_width])

    return repair_schedule




    

    
    
    