# # /// script
# # requires-python = ">=3.11"
# # dependencies = [
# #   "httpx",
# #   "pandas",
# #   "matplotlib",
# # ]
# # ///

# # Rest of your script starts here
# import pandas as pd
# import matplotlib.pyplot as plt
# import httpx

# # Example code
# def main(file_path):
#     data = pd.read_csv(file_path)
#     print(data.head())


# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pandas",
#   "seaborn",
#   "matplotlib",
#   "httpx",
#   "openai",
#   "seaborn",
# ]
# ///

import os
import sys
import json
import logging
import base64
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import httpx
from typing import List, Dict, Any
import traceback
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AutomatedAnalysis:
    def __init__(self, dataset_path: str):
        """
        Initialize the automated analysis with the given dataset.
        
        :param dataset_path: Path to the dataset file
        """
        try:
            logger.info(f"Initializing analysis for dataset: {dataset_path}")
            self.dataset_path = dataset_path
            
            # Validate CSV file
            if not os.path.exists(dataset_path):
                raise FileNotFoundError(f"Dataset file not found: {dataset_path}")
            
            # Try multiple encodings
            encodings_to_try = [
                'utf-8', 
                'latin-1', 
                'iso-8859-1', 
                'cp1252', 
                'utf-16'
            ]
            
            for encoding in encodings_to_try:
                try:
                    self.df = pd.read_csv(dataset_path, encoding=encoding)
                    logger.info(f"Successfully loaded dataset using {encoding} encoding with {len(self.df)} rows")
                    break
                except (UnicodeDecodeError, pd.errors.ParserError):
                    logger.warning(f"Failed to read file with {encoding} encoding")
                    continue
            else:
                raise ValueError(f"Could not read the CSV file with any of the tried encodings")
            
            # Validate AI Proxy Token
            # self.aiproxy_token = os.environ.get("AIPROXY_TOKEN")
            self.aiproxy_token = "eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IjIyZjIwMDExOTNAZHMuc3R1ZHkuaWl0bS5hYy5pbiJ9.CEi7xBI23rsAvNmTw2lE236c0r3tpoXsQsUGhBBywuo"
            if not self.aiproxy_token:
                logger.error("AIPROXY_TOKEN environment variable is not set")
                raise ValueError("AIPROXY_TOKEN environment variable must be set")
        
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def _generate_generic_analysis(self) -> Dict[str, Any]:
        """
        Perform generic data analysis.
        
        :return: Dictionary with analysis results
        """
        analysis = {
            "basic_info": {
                "total_rows": len(self.df),
                "total_columns": len(self.df.columns),
                "column_types": {col: str(dtype) for col, dtype in self.df.dtypes.items()}
            },
            "missing_values": self.df.isnull().sum().to_dict(),
            "descriptive_stats": {}
        }
        
        # Convert descriptive stats to dictionary with string representation
        try:
            desc_stats = self.df.describe()
            for col, stats in desc_stats.to_dict().items():
                analysis["descriptive_stats"][col] = {k: str(v) for k, v in stats.items()}
        except Exception as e:
            logger.warning(f"Could not generate descriptive statistics: {e}")
        
        # Try to find correlations if numeric columns exist
        numeric_columns = self.df.select_dtypes(include=['float64', 'int64']).columns
        if len(numeric_columns) > 1:
            try:
                correlation_matrix = self.df[numeric_columns].corr()
                # Convert correlation matrix to dictionary with string representation
                analysis["correlation_matrix"] = {
                    str(col1): {str(col2): str(val) for col2, val in row.items()}
                    for col1, row in correlation_matrix.to_dict().items()
                }
            except Exception as e:
                logger.warning(f"Could not generate correlation matrix: {e}")
        
        return analysis
    
    def _call_llm(self, messages: List[Dict[str, str]], functions: List[Dict] = None) -> str:
        """
        Call the OpenAI-compatible LLM via AI Proxy.
        
        :param messages: List of message dictionaries
        :param functions: Optional list of function definitions
        :return: LLM response
        """
        # Fallback narrative generation if LLM call fails
        def generate_fallback_narrative(analysis):
            narrative = f"""
            # Data Analysis Narrative

            ## Dataset Overview

            - *Total Rows*: {analysis['basic_info']['total_rows']}
            - *Total Columns*: {analysis['basic_info']['total_columns']}

            ## Column Types
            {', '.join([f"{col}: {dtype}" for col, dtype in analysis['basic_info']['column_types'].items()])}

            ## Missing Values
            {', '.join([f"{col}: {count}" for col, count in analysis.get('missing_values', {}).items() if count > 0])}

            ## Key Insights

            1. *Data Composition*
            - The dataset contains {analysis['basic_info']['total_rows']} rows and {analysis['basic_info']['total_columns']} columns.
            - Column types include: {', '.join(set(analysis['basic_info']['column_types'].values()))}

            2. *Data Quality*
            - Missing values were detected in some columns, which may require further investigation.

            3. *Potential Next Steps*
            - Clean missing data
            - Perform more detailed statistical analysis
            - Consider feature engineering based on column types

            ## Limitations of This Analysis
            - Automated narrative generation encountered an issue
            - A basic narrative has been generated as a fallback
            """
            return narrative

        # Attempt to use AI Proxy
        try:
            headers = {
                "Authorization": f"Bearer {self.aiproxy_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "gpt-4o-mini",
                "messages": messages,
                **({"functions": functions} if functions else {})
            }
            
            # Try multiple endpoints
            endpoints = [
                "http://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
            ]
            
            for endpoint in endpoints:
                try:
                    with httpx.Client(timeout=30.0) as client:
                        response = client.post(
                            endpoint, 
                            headers=headers, 
                            json=payload
                        )
                        response.raise_for_status()
                        
                        response_json = response.json()
                        if 'choices' in response_json and response_json['choices']:
                            return response_json['choices'][0]['message']['content']
                
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    logger.warning(f"Failed endpoint {endpoint}: {e}")
                    continue
            
            # If all endpoints fail, use fallback
            logger.error("All LLM endpoints failed")
            return generate_fallback_narrative(self._generate_generic_analysis())
        
        except Exception as e:
            logger.error(f"Unexpected error in LLM call: {e}")
            logger.error(traceback.format_exc())
            
            # Use fallback narrative if possible
            try:
                return generate_fallback_narrative(self._generate_generic_analysis())
            except Exception:
                return """
                # Data Analysis Narrative

                ## Error

                An unexpected error occurred during narrative generation.
                Please review the dataset manually.
                """
    
    def _create_visualizations(self, analysis: Dict[str, Any]):
        """
        Create visualizations based on the analysis.
        
        :param analysis: Dictionary containing analysis results
        """
        try:
            plt.figure(figsize=(15, 10))
            plt.subplots_adjust(hspace=0.4, wspace=0.4)
            
            # Visualization 1: Missing Values
            plt.subplot(2, 2, 1)
            missing_values = pd.Series(analysis.get('missing_values', {}))
            missing_values = missing_values[missing_values > 0]
            
            if not missing_values.empty:
                missing_values.plot(kind='bar')
                plt.title('Missing Values by Column')
                plt.xlabel('Columns')
                plt.ylabel('Number of Missing Values')
                plt.xticks(rotation=45, ha='right')
            else:
                plt.text(0.5, 0.5, 'No Missing Values', 
                         horizontalalignment='center', 
                         verticalalignment='center')
                plt.title('Missing Values')
            
            # Visualization 2: Numeric Column Distribution
            plt.subplot(2, 2, 2)
            numeric_columns = [col for col, dtype in analysis['basic_info']['column_types'].items() 
                               if 'float' in dtype.lower() or 'int' in dtype.lower()]
            
            if numeric_columns:
                # Select the first numeric column for distribution
                first_numeric_col = numeric_columns[0]
                column_data = self.df[first_numeric_col]
                
                sns.histplot(column_data, kde=True)
                plt.title(f'Distribution of {first_numeric_col}')
                plt.xlabel(first_numeric_col)
                plt.ylabel('Frequency')
            else:
                plt.text(0.5, 0.5, 'No Numeric Columns', 
                         horizontalalignment='center', 
                         verticalalignment='center')
                plt.title('Column Distribution')
            
            # Visualization 3: Correlation Heatmap
            plt.subplot(2, 2, (3, 4))
            correlation_matrix = analysis.get('correlation_matrix', {})
            
            if correlation_matrix:
                # Convert correlation matrix to DataFrame with numeric values
                corr_df = pd.DataFrame({
                    col1: {col2: float(val) for col2, val in row.items()}
                    for col1, row in correlation_matrix.items()
                })
                
                plt.figure(figsize=(10, 8))
                sns.heatmap(corr_df, annot=True, cmap='coolwarm', center=0, 
                            square=True, linewidths=0.5, cbar_kws={"shrink": .8})
                plt.title('Correlation Heatmap')
                plt.tight_layout()
            else:
                plt.text(0.5, 0.5, 'No Correlation Data', 
                         horizontalalignment='center', 
                         verticalalignment='center')
                plt.title('Correlation Heatmap')
            
            # Save visualizations
            plt.tight_layout()
            plt.savefig('analysis_visualization.png', dpi=300, bbox_inches='tight')
            plt.close('all')
            
            logger.info("Visualizations created successfully")
        
        except Exception as e:
            logger.error(f"Error creating visualizations: {e}")
            logger.error(traceback.format_exc())
            
            # Fallback: Create a simple error visualization
            plt.figure(figsize=(10, 6))
            plt.text(0.5, 0.5, f'Visualization Error:\n{str(e)}', 
                     horizontalalignment='center', 
                     verticalalignment='center')
            plt.title('Visualization Error')
            plt.axis('off')
            plt.savefig('analysis_visualization.png')
            plt.close('all')
    
    def generate_narrative(self, analysis: Dict[str, Any]) -> str:
        """
        Generate a narrative about the data analysis.
        
        :param analysis: Dictionary containing analysis results
        :return: Markdown narrative
        """
        try:
            # Safely convert analysis to a string representation
            def safe_str(obj):
                try:
                    return str(obj)
                except Exception:
                    return "Unable to convert to string"
            
            # Prepare narrative prompt with safely converted data
            prompt = f"""
            Write a compelling narrative about this dataset analysis:
            
            Dataset Overview:
            - Total Rows: {safe_str(analysis['basic_info']['total_rows'])}
            - Total Columns: {safe_str(analysis['basic_info']['total_columns'])}
            - Column Types: {json.dumps(analysis['basic_info']['column_types'], indent=2)}
            
            Missing Values Summary:
            {json.dumps(analysis.get('missing_values', {}), indent=2)}
            
            Descriptive Statistics:
            {json.dumps(analysis.get('descriptive_stats', {}), indent=2)}
            
            Correlation Matrix (if available):
            {json.dumps(analysis.get('correlation_matrix', {}), indent=2)}
            
            Please structure the narrative with:
            1. Brief data description
            2. Key insights from the analysis
            3. Potential implications or recommendations
            
            Use markdown formatting. Be creative and engaging!
            """
            
            # Call LLM with the prepared prompt
            narrative = self._call_llm([{"role": "user", "content": prompt}])
            
            return narrative
        
        except Exception as e:
            logger.error(f"Error generating narrative: {e}")
            logger.error(traceback.format_exc())
            return f"""
            # Data Analysis Narrative

            ## Error Generating Narrative

            Unfortunately, an error occurred while attempting to generate the narrative for this dataset.

            *Error Details:*
            {str(e)}

            Please check the dataset and try again.
            """
    
    def run_analysis(self):
        """
        Run the complete automated analysis workflow.
        """
        # Perform generic analysis
        self.analysis = self._generate_generic_analysis()
        
        # Create visualizations
        self._create_visualizations(self.analysis)
        
        # Generate narrative
        narrative = self.generate_narrative(self.analysis)
        
        # Write narrative to README.md
        with open('README.md', 'w') as f:
            f.write(narrative)
        
        print("Analysis complete. Check README.md and analysis_visualization.png")

def main():
    try:
        # Validate command-line arguments
        if len(sys.argv) != 2:
            logger.error("Incorrect usage. Please provide a CSV file.")
            print("Usage: uv run autolysis.py <dataset.csv>")
            sys.exit(1)
        
        # Validate file extension
        dataset_path = sys.argv[1]
        if not dataset_path.lower().endswith('.csv'):
            logger.error(f"Invalid file type: {dataset_path}. Must be a CSV file.")
            print("Error: Input must be a CSV file")
            sys.exit(1)
        
        # Determine output directory based on dataset name
        dataset_name = os.path.splitext(os.path.basename(dataset_path))[0]
        output_dir = dataset_name.lower()
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Run analysis
        try:
            analyzer = AutomatedAnalysis(dataset_path)
            analyzer.run_analysis()
            logger.info("Analysis completed successfully")
            
            # Move outputs to dataset-specific directory
            readme_path = 'README.md'
            png_files = [f for f in os.listdir('.') if f.endswith('.png')]
            
            if os.path.exists(readme_path):
                # If file already exists, overwrite it
                shutil.move(readme_path, os.path.join(output_dir, readme_path))
            
            for png_file in png_files:
                # If file already exists, overwrite it
                shutil.move(png_file, os.path.join(output_dir, png_file))
            
            print(f"Analysis results saved in {output_dir} directory")
        
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            logger.error(traceback.format_exc())
            print(f"Error during analysis: {e}")
            sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("Analysis interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__== "__main__":
    main()
