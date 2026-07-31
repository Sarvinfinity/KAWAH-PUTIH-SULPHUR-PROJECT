"""
Run all visualizations and forecasting (1h + 24h windows).
"""
from generate_visualizations import main as run_visualizations
from forecasting import run_all_forecasts


def main():
    print('=' * 60)
    print('STEP 1: Generating all visual representations')
    print('=' * 60)
    run_visualizations()

    print('\n' + '=' * 60)
    print('STEP 2: Running forecasting (1-hour & 24-hour windows)')
    print('=' * 60)
    run_all_forecasts()

    print('\n' + '=' * 60)
    print('Analysis complete.')
    print('  Visualizations: outputs/plots/')
    print('  Forecasts:      outputs/predictions/')
    print('=' * 60)


if __name__ == '__main__':
    main()
