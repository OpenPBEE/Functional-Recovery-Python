def plot_results(outputs_dir, p_gantt=50):
    """
    Plot Functional Recovery Plots For a Single Model and Single Intensity
    
    Parameters
    ----------
    output dir: string
        Directory of outputs
    p_gantt: float
        percentile of functional recovery time to plot for the gantt chart
        default: 50 = 50th percentile of functional recovery time (median)
    
    """
    import os
    import json
    import pandas as pd
    
    # from plotters import main_plot_functionality
    # Plot Functional Recovery Plots For a Single Model and Single Intensity
    
    ## Define User inputs
    
    # Load systems information
    systems = pd.read_csv(os.path.join(os.path.dirname(__file__), 'src', 'atc138', 'data', 'systems.csv'))
    systems = systems['name']
    
    # outputs will save to a directory with this name
    plot_dir = outputs_dir +'/plots' # Directory where the plots will be saved
    
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