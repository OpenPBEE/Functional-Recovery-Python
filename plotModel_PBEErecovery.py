def plot_results(model_name):
    """
    Plot Functional Recovery Plots For a Single Model and Single Intensity
    
    Parameters
    ----------
    model_name: string
        Name of the model. Inputs are expected to be in a directory with this 
        name. Outputs will save to a directory with this name
    
    """
    import os
    import json
    import pandas as pd
    
    # from plotters import main_plot_functionality
    # Plot Functional Recovery Plots For a Single Model and Single Intensity
    
    ## Define User inputs
    
    # Load systems information
    systems = pd.read_csv(os.path.join(os.path.dirname(__file__), 'static_tables', 'systems.csv'))
    systems = systems['name']
    
    # outputs will save to a directory with this name
    outputs_dir = os.path.join(os.path.dirname(__file__), 'outputs/'+model_name) # Directory where the assessment outputs are saved
    plot_dir = outputs_dir +'/plots' # Directory where the plots will be saved
    p_gantt = 50 # percentile of functional recovery time to plot for the gantt chart
                  #e.g., 50 = 50th percentile of functional recovery time
    
    ## Import Packages
    from plotters import main_plot_functionality
    
    ## Load Assessment Output Data
    f = open(os.path.join(outputs_dir, 'recovery_outputs.json'))
    functionality= json.load(f)
    
    ## Create plot for single intensity assessment of PBEE Recovery
    main_plot_functionality.main_plot_functionality(functionality, plot_dir, p_gantt, systems)

if __name__ == '__main__':

    model_name = 'ICSB'

    plot_results(model_name)