# Quantitative synthetic survey automated with JTBD theory

## Overview
!https://railsware.com/blog/wp-content/uploads/2019/05/1520-x-1571_Image-3-1-991x1024.png

The purpose of this project is: use LLMs (ChatGPT) to answer synthetic surveys for football clubs with given personas according to Jobs-to-be-done method and pre-given ODI statements. 

## Setup

```
git clone https://github.com/dophat1/jtbd-synthetic-survey

cd jtbd-synthetic-survey

python -m venv (venv_name)

venv_name\Scripts\activate.ps1

pip install -r requirements.txt

streamlit synthetic_survey.py
```

After that, open the link streamlit provide and see the GUI on your browser. Then create your openAI key in https://platform.openai.com/ then paste it in the openAI key field. Then run the create personas if you dont have a preset of personas. If you have it already, upload it as .csv data.

In this case, we model personas based on Big Five model.

Then run the survey and wait for the result. 

## Theory

1. What is JTBD ?
Its a theory developed by Anthony Ulwick with the goal of finding the real needs of the customers qualitatively and quantitatively. 

2. How to do it step by step ?

I. Define the Customer
II. Define the Job-to-be-Done
III. Uncover Customer Needs
- The Universal Job Map
- The Desired Outcome Statement
IV. Find Segments of Opportunity <--- This project is for this part
V. Define the Value Proposition
VI. Conduct the Competitive Analysis
VII. Formulate the Innovation Strategy
VIII. Target Hidden Growth Opportunities <---- And this part
- The Opportunity Algorithm
- The Opportunity Landscape
IX. Formulate the Market Strategy
X. Formulate the Product Strategy

3. Automate the survey AFTER getting ODI statements

The Outcome Driven Statement (ODI statement) is a single statement formulate from the need of core job executor. 

The formular is: 

Outcome statement = direction of improvement + performance metric + object of control + contextual clarifier

Example: minimize the time to find a job. 

Read more on: https://www.ki-insights.com/wp-content/uploads/2024/05/Ulwick.pdf

Every job statement will be formulated into outcome statement form like above. And the survey created using the synthetic_survey.py is giving each of these ODI 2 scales from 1 to 10: importance and satisfaction. The llms will take the generated personas to answer these 2 scalas of all ODI statement. Then we have the dataset.

If you want to change the questions in the survey, go to synthetic_survey.py, in QUESTIONS = [] global variables.  

After that, we need to segment these results based on importance score to find natural groups (cluster based on needs, not demographics, jobs,...). Use the segment_respondents.py

```
# Usage 

python segment_respondents.py <input_file.csv> [output_file.csv] [force_k]
       
# Example: 

python segment_respondents.py results.csv results_segments.csv 3

```
Where the results.csv is the data answered by the llm, and the results_segments.csv is the file after clustering all the answerers into group based on their need. Force k is used for forcing the number of group (Ulwick suggests normally there is 3-5 groups). If no force k then it will run silouhette point calculation for each k by looping and find the optimum. 

4. Opportunity score

After having cluster, we use the opportunity algorithm to find where needs the most improvement therefore start designing strategy. Due to restrain on this, the strategy part is on Ulwick book and will not be detailed discussed here. 

Opportunity algorithm (for each questions in the survey):

Opportunity score = outcome importance + max(outcome importance – outcome satisfaction, 0)

We average out all the importance and satisfaction for each question for each groups segmented before in the list, then apply the formular to get the opportunity score for each questions. 

As a rule of thumb, opp score > 10 should be a good place to start innovating. 

```
# Usage 
    python opportunity_scores_per_segment.py <segments_file.csv> [output_file.csv]
# Example: 
    python opportunity_scores_per_segment.py results_segments.csv

```

From the result, you can do analysis on that data (an example is in jtbd_analysis.ipynb in the same repository). 

5. Strategy

After having the opportunity score for each segment, you will understand where is the pain point of the customers on each segment. Now its your turn to figuring out the strategy for innovation. Learn more on these strategy on the book of Ulwick - JTBD From Theory to practice. Good luck !


