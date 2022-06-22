# Databricks notebook source
# MAGIC %pip install great-expectations

# COMMAND ----------

#dbutils.fs.mkdirs('/Filestores/GE_spark_tutorial')

# COMMAND ----------

raw_df = spark.read.option("header", True).csv("/Filestores/GE_spark_tutorial/Kickstarter_projects_Feb19.csv")
display(raw_df)

# COMMAND ----------

raw_df.createOrReplaceTempView("Campaigns")

# COMMAND ----------

raw_df.toPandas()

# COMMAND ----------

from great_expectations.dataset import SparkDFDataset

raw_test_df_profiling = SparkDFDataset(raw_df)
raw_test_df = SparkDFDataset(raw_df)
type(raw_test_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ###Profiling the data

# COMMAND ----------

from great_expectations.profile.basic_dataset_profiler import BasicDatasetProfiler

expectation_suite_based_on_profiling, validation_result_based_on_profiling = raw_test_df_profiling.profile(BasicDatasetProfiler)

print(type(expectation_suite_based_on_profiling),'\n',type(validation_result_based_on_profiling))

# COMMAND ----------

# MAGIC %md
# MAGIC ###Visualizing the profiling result and expectation came from profiling

# COMMAND ----------

# import the renderer who will basically create the document content
from great_expectations.render.renderer import ProfilingResultsPageRenderer, ExpectationSuitePageRenderer
# import the view template who will basically convert the document content to HTML
from great_expectations.render.view import DefaultJinjaPageView

profiling_result_document_content = ProfilingResultsPageRenderer().render(validation_result_based_on_profiling)
expectation_based_on_profiling_document_content = ExpectationSuitePageRenderer().render(expectation_suite_based_on_profiling)

print(type(profiling_result_document_content),'\n',type(expectation_based_on_profiling_document_content))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Generate HTML report

# COMMAND ----------

profiling_result_HTML = DefaultJinjaPageView().render(profiling_result_document_content) 
expectation_based_on_profiling_HTML = DefaultJinjaPageView().render(expectation_based_on_profiling_document_content)

displayHTML(profiling_result_HTML)

# COMMAND ----------

# MAGIC %md 
# MAGIC #UNIT TESTING OF DATA

# COMMAND ----------

# MAGIC %md
# MAGIC ###1. Check for mandatory columns

# COMMAND ----------

MANDATORY_COLUMNS = [
  "id",
  "currency",
  "main_category",
  "launched_at",
  "deadline",
  "country",
  "status",
  "usd_pledged"
]

# COMMAND ----------

for column in MANDATORY_COLUMNS:
  try:
    assert raw_test_df.expect_column_to_exist(column).success, f"FAILED : Mandatory column {column} does not exists."
    print(f"PASSES : Column {column} exists")
  except AssertionError as e:
    print(e)

# COMMAND ----------

# MAGIC %md
# MAGIC ###2. Mandatory columns should not be null

# COMMAND ----------

for column in MANDATORY_COLUMNS:
  try:
    test_result = raw_test_df.expect_column_values_to_not_be_null(column)
    assert test_result.success, f"FAILED : {test_result.result['unexpected_count']} of {test_result.result['element_count']} items in {column} are null."
    print(f"PASSED : All items in {column} are not null")
  except AssertionError as e:
    print(e)    

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3. Check for valid data format

# COMMAND ----------

test_result =  raw_test_df.expect_column_values_to_match_strftime_format('launched_at','%Y-%m-%d %H:%M:%S')
f"""{round(test_result.result['unexpected_percent'], 2)}% is not a valid date time format"""

# COMMAND ----------

test_result =  raw_test_df.expect_column_values_to_match_strftime_format('deadline','%Y-%m-%d %H:%M:%S')
f"""{round(test_result.result['unexpected_percent'], 2)}% is not a valid date time format"""

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4. Check for uniqueness

# COMMAND ----------

test_result = raw_test_df.expect_column_values_to_be_unique("id")
failed_msg = " ".join([f"""{test_result.result['unexpected_count']} of {test_result.result['element_count']} items""",
                       f"""or {round(test_result.result['unexpected_percent'],2)}% are not unique: FAILED"""])
print(f"""{'Column id is unique: PASSED' if test_result.success else failed_msg}""")

# COMMAND ----------

custom_validation = raw_test_df.validate()

# COMMAND ----------

custom_validation["meta"]["expectation_suite_name"] = "raw_data"

# COMMAND ----------

from great_expectations.render.renderer import ValidationResultsPageRenderer
# import the view template who will basically convert the document content to HTML
from great_expectations.render.view import DefaultJinjaPageView

validation_result_document_content = ValidationResultsPageRenderer().render(custom_validation)
validation_result_HTML = DefaultJinjaPageView().render(validation_result_document_content)

# COMMAND ----------

displayHTML(validation_result_HTML)

# COMMAND ----------

import time

# saving the html files
def save_file(**files):
  for file_name, file_content in files.items():
    loc = f'/mnt/data-lake/test_incubyte/diwakar/great_expectations_{str(time.time()).split(".")[0]}/{file_name}'
    dbutils.fs.put(loc, file_content)
    print(f'{file_name} is put --> {loc}')
    
save_file(**{
  'validation.html': validation_result_HTML
})

# COMMAND ----------

# send validation result to Microsoft teams
import requests
import json
from great_expectations.render.renderer.microsoft_teams_renderer import MicrosoftTeamsRenderer
#from great_expectations.render.renderer.slack_renderer import SlackRenderer

requests.post("https://incubytein.webhook.office.com/webhookb2/b9be248a-94a5-4a94-a556-f4c71d2de126@05b07524-f2af-411a-b5a9-a5fee6228712/IncomingWebhook/fe3bf821c59b46afab3874d8bdfe56cd/95ae853b-30a8-4d1f-8805-5dcaca996f99", json = MicrosoftTeamsRenderer().render(custom_validation))

# COMMAND ----------

# MAGIC %md
# MAGIC #FILTER DATA BASED ON BUSINESS RULES

# COMMAND ----------

# MAGIC %md
# MAGIC ###1. Assign filter variables based on business rules

# COMMAND ----------

MAIN_CATEGORIES = [
    'art',
    'publishing',
    'film & video',
    'technology',
    'journalism',
    'food',
    'dance',
    'photography',
    'games',
    'crafts',
    'music',
    'comics',
    'theater',
    'design'    
]
ASSESSMENT_YEAR = ['2017','2018']
COUNTRY = 'US'
CURRENCY = 'USD'

# COMMAND ----------

# MAGIC %md
# MAGIC ###2. Custom assessment year reference

# COMMAND ----------

import pandas as pd

assessment_year_reference = {
    'assessment_year': ['2017', '2018'], 
    'period_start_dt': ['2016-07-01', '2017-07-01'],
    'period_end_dt': ['2017-06-30', '2018-06-30'],
}
ay_df = pd.DataFrame(data=assessment_year_reference)
ay_df

# COMMAND ----------

spark_ay_df = spark.createDataFrame(ay_df) 
spark_ay_df.createOrReplaceTempView("assessment_year_ref")

# COMMAND ----------

# MAGIC %md
# MAGIC ###3. Applying filter transformation

# COMMAND ----------

filtered_df = spark.sql(f"""
    SELECT id,
           name,
           currency,
           main_category,
           launched_at,
           deadline,
           goal_usd,
           country,
           usd_pledged,
           status,
           assessment_year
    FROM (SELECT t.*,
               ay.assessment_year,
               row_number() OVER (
                   PARTITION BY t.id
                   ORDER BY t.launched_at, 
                            ay.assessment_year DESC) row_no
          FROM CAMPAIGNS t
          INNER JOIN assessment_year_ref ay
              ON TO_DATE(t.launched_at) <= ay.period_end_dt 
              AND t.deadline > ay.period_start_dt
          WHERE country = '{COUNTRY}'
          AND status = 'successful'
          AND main_category IN ('{"','".join(MAIN_CATEGORIES)}')
          AND ay.assessment_year IN ('{"','".join(ASSESSMENT_YEAR)}')
          AND currency = '{CURRENCY}'
   ) WHERE row_no = 1 
    """)

# COMMAND ----------

filtered_df.createOrReplaceTempView("FILTERED_CAMPAIGNS")

# COMMAND ----------

filtered_df.toPandas()

# COMMAND ----------

# MAGIC %md
# MAGIC #UNIT TEST ON FILTERED DATA

# COMMAND ----------

filtered_test_df = SparkDFDataset(filtered_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ###1. Check if main_category within scope

# COMMAND ----------

test_result = filtered_test_df.expect_column_values_to_be_in_set("main_category", MAIN_CATEGORIES)
print(f"""Categories are within scope: {'PASSED' if test_result.success else 'FAILED'}""")

# COMMAND ----------

# MAGIC %md
# MAGIC ###2. Check if country is equal to "US"

# COMMAND ----------

test_result = filtered_test_df.expect_column_values_to_be_in_set("country", ["US"])
print(f"""All campaigns are done in the country of USA: {'PASSED' if test_result.success else 'FAILED'}""")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3. Check if status = 'success'

# COMMAND ----------

test_result = filtered_test_df.expect_column_values_to_be_in_set("status", ["successful"])
print(f"""All campaigns are successful: {'PASSED' if test_result.success else 'FAILED'}"""

# COMMAND ----------

# MAGIC %md
# MAGIC ###4. Check if currency = 'USD'

# COMMAND ----------

test_result = filtered_test_df.expect_column_values_to_be_in_set("currency", ["USD"])
print(f"""All campaigns are successful: {'PASSED' if test_result.success else 'FAILED'}""")

# COMMAND ----------

# MAGIC %md
# MAGIC ###5. Check if mandatory columns are not null

# COMMAND ----------

for column in MANDATORY_COLUMNS:
    try:
        test_result = filtered_test_df.expect_column_values_to_not_be_null(column)
        assert test_result.success, f"{test_result.result['unexpected_count']} of {test_result.result['element_count']} items in column {column} are null: FAILED"
        print(f"All items in column {column} are not null: PASSED")
    except AssertionError as e:
        print(e)

# COMMAND ----------

# MAGIC %md
# MAGIC ###6. Check if id is unique in each assessment year

# COMMAND ----------

test_result = filtered_test_df.expect_compound_columns_to_be_unique(["id", "assessment_year"])
print(f"""id column is unique for each assessment year: {'PASSED' if test_result.success else 'FAILED'}""")

# COMMAND ----------

# MAGIC %md
# MAGIC ###7. Check if launched_date is valid datetime format

# COMMAND ----------

test_result =  filtered_test_df.expect_column_values_to_match_strftime_format('launched_at','%Y-%m-%d %H:%M:%S')
f"""launched_at column values are compliant to datetime format: {'PASSED' if test_result.success else 'FAILED'}"""

# COMMAND ----------

# MAGIC %md
# MAGIC ###8. Check if deadline is a valid datetime format

# COMMAND ----------

test_result =  filtered_test_df.expect_column_values_to_match_strftime_format('deadline','%Y-%m-%d %H:%M:%S')
f"""deadline column values are compliant to datetime format: {'PASSED' if test_result.success else 'FAILED'}"""

# COMMAND ----------

custom_validation = raw_test_df.validate()

# COMMAND ----------

custom_validation["meta"]["expectation_suite_name"] = "raw_test"

# COMMAND ----------

from great_expectations.render.renderer import ValidationResultsPageRenderer
# import the view template who will basically convert the document content to HTML
from great_expectations.render.view import DefaultJinjaPageView

validation_result_document_content = ValidationResultsPageRenderer().render(custom_validation)
validation_result_HTML = DefaultJinjaPageView().render(validation_result_document_content)

# COMMAND ----------

displayHTML(validation_result_HTML)
