from twitchio.ext import commands
import random
import io
import os
import gspread
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict



class Bot(commands.Bot):

    def __init__(self):
        # Initialise our Bot with our access token, prefix and a list of channels to join on boot...
        global trivia_switch,credentials,gc,channel
        channel = os.environ.get('CHANNEL_NAME')
        super().__init__(token=os.environ.get('TOKEN'), prefix='!', initial_channels=[channel])
        self.questions_and_answers = []
        self.user_scores = {}
        trivia_switch=1
        credentials_json = os.environ.get("CREDS")
        credentials = json.loads(credentials_json)
        gc = gspread.service_account_from_dict(credentials)
        

    async def event_ready(self):
        # We are logged in and ready to chat and use commands...
        print(f'Logged in as | {self.nick}')
        print(f'User id is | {self.user_id}')
        self.load_data()
        # Start the scheduling task
        loop = asyncio.get_event_loop()
        loop.create_task(self.autosave_score_schedule_function())
        # Run the event loop
        #loop.run_forever()

    async def auto_score_saver(self):
        score_sheet = gc.open(f"{channel} score sheet").sheet1  # Replace with your sheet name
            
            # Retrieve the existing scores from the Google Sheet
        existing_scores = score_sheet.get_all_records()
        score_dict = {row['User']: int(row['Score']) for row in existing_scores}
            
            # Update scores in the dictionary
        for user, score in self.user_scores.items():
                if user in score_dict:
                    if score > score_dict[user]:
                        score_dict[user] = score
                    elif score < score_dict[user]:
                        score_dict[user] += score
                else:
                    score_dict[user] = score

            # Clear the existing data in the Google Sheet
        score_sheet.clear()
            
            # Write the updated scores to the Google Sheet
        updated_scores = [['User', 'Score']]
        for user, score in score_dict.items():
                updated_scores.append([user, score])
        score_sheet.update(updated_scores)
            
            # Update the scores dictionary with the updated scores
        self.user_scores = score_dict
        print('Scores Saved Automatically')


    async def autosave_score_schedule_function(self):
        while True:
            # Call your function to save the scores
            await self.auto_score_saver()
            

            # Wait for 1 minutes
            await asyncio.sleep(60)  # 10 minutes = 600 seconds

        

    def load_data(self):
        global currentAnswer, currentQuestion, gc
        currentAnswer = None
        currentQuestion = None
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        gc = gspread.service_account_from_dict(credentials)
        sheet = gc.open('TriviaDataset').sheet1
        data = sheet.get_all_records()
        self.questions_and_answers = [(row['Question'], row['Answer']) for row in data if row['Question'] and row['Answer']]
        score_sheet = gc.open(f"{channel} score sheet").sheet1  # Replace with your sheet name
        data = score_sheet.get_all_values()
        for row in data[1:]:  # Exclude the header row
            self.user_scores[row[0]] = int(row[1])
        
        print('Scores loaded!')

    

    
    @commands.command(name='LoadQuestions')
    async def load_questions_command(self, ctx):
        if ctx.author.is_mod or ctx.author.name == ctx.channel.name:
            global currentAnswer, currentQuestion
            currentAnswer = None
            currentQuestion = None
            scope = ['https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive']
            sheet = gc.open('TriviaDataset').sheet1
            data = sheet.get_all_records()
            self.questions_and_answers = [(row['Question'], row['Answer']) for row in data if row['Question'] and row['Answer']]
            await ctx.send("Questions Loaded!")
        else:
            await ctx.send("Sorry, only mods and the channel owner can run this command.")




    @commands.command(name='TriviaTurnOn')
    async def trivia_on_command(self, ctx):
        if ctx.author.is_mod or ctx.author.name == ctx.channel.name:
            global trivia_switch
            trivia_switch = 1
            print(f"trivia_switch value: {trivia_switch}")
            await ctx.send("Trivia is now On")
        else:
            await ctx.send("Sorry, only mods and the channel owner can run this command.")


    @commands.command(name='TriviaTurnOff')
    async def trivia_off_command(self, ctx):
        if ctx.author.is_mod or ctx.author.name == ctx.channel.name:
            global trivia_switch
            trivia_switch = 0
            print(f"trivia_switch value: {trivia_switch}")
            await ctx.send("Trivia Is now Off")
        else:
            await ctx.send("Sorry, only mods and the channel owner can run this command.")



    @commands.command(name='SwitchValue')
    async def switch_value_command(self, ctx):
        if ctx.author.is_mod or ctx.author.name == ctx.channel.name:
            await ctx.send(f"Trivia Switch is {str(trivia_switch)}")
        else:
            await ctx.send("Sorry, only mods and the channel owner can run this command.")

    @commands.command(name='CurrentAnswer')
    async def current_answer_call(self, ctx):
        global currentAnswer
        if ctx.author.is_mod or ctx.author.name == ctx.channel.name:
            await ctx.send(currentAnswer)
        else:
            await ctx.send("Sorry, only mods and the channel owner can run this command.")

    @commands.command(name='CurrentQuestion')
    async def current_question_call(self, ctx):
        global currentQuestion, currentAnswer, trivia_switch
        if trivia_switch==1:
            if not currentQuestion:
                
                    currentQuestion, answer = random.choice(self.questions_and_answers)
                    currentAnswer = str(answer)
                    await ctx.send(currentQuestion)
            else:
                await ctx.send(currentQuestion)
        else:
            await ctx.send("Trivia is turned off at the moment, ask the channel owner to turn it on.")


    @commands.command(name='Guess')
    async def guess_command(self, ctx: commands.Context, *, guess_text: str):
        global currentAnswer
        global currentQuestion
        
        if not currentAnswer:
            response = f"Sorry {ctx.author.name}! There is no trivia question to guess for right now! Type !CurrentQuestion to start a new round!"
        elif guess_text.lower() == str(currentAnswer).lower():
            if ctx.author.name not in self.user_scores:
                self.user_scores[ctx.author.name] = 1
            else:
                self.user_scores[ctx.author.name] += 1
                
            response = f"Correct, {ctx.author.name}! Your score is now {self.user_scores[ctx.author.name]}."
            currentAnswer = None
            currentQuestion = None
        else:
            try:
                guess_val = float(guess_text)
                answer_val = float(currentAnswer)
                if guess_val == answer_val:
                    if ctx.author.name not in self.user_scores:
                        self.user_scores[ctx.author.name] = 1
                    else:
                        self.user_scores[ctx.author.name] += 1
                        
                    response = f"Correct, {ctx.author.name}! Your score is now {self.user_scores[ctx.author.name]}."
                    currentAnswer = None
                    currentQuestion = None
                else:
                    response = f"Incorrect, {ctx.author.name}! Your score remains {self.user_scores.get(ctx.author.name, 0)}."
            except ValueError:
                response = f"Incorrect, {ctx.author.name}! Your score remains {self.user_scores.get(ctx.author.name, 0)}."
                
        await ctx.send(response)


    @commands.command(name='Score')
    async def score_command(self, ctx: commands.Context):
        if ctx.author.name in self.user_scores:
            await ctx.send(f"{ctx.author.name}, your score is {self.user_scores[ctx.author.name]}.")
        else:
            await ctx.send(f"{ctx.author.name}, you haven't answered any questions correctly since the last save")
    
    @commands.command(name='TriviaHelp')
    async def help_command(self, ctx):
        help_text = f"Hello {ctx.author.name}, Go here to get help: http://notepad.link/share/UqD07nYptBf3wQqta73o"
        # https://notepad.link/fZDFp Is the editable note link for the above
        await ctx.send(help_text)

    @commands.command(name='TriviaSkip')
    async def trivia_mod_command(self, ctx):
        if ctx.author.is_mod or ctx.author.name == ctx.channel.name:
            global currentQuestion
            currentQuestion = None
            await self.current_question_call(ctx)
        else:
            await ctx.send("Sorry, only mods and the channel owner can run this command.")

    @commands.command(name='SaveScores')
    async def update_score_command(self, ctx: commands.Context):
        if ctx.author.is_mod or ctx.author.name == ctx.channel.name:
            # Open the Google Sheet
            score_sheet = gc.open(f"{channel} score sheet").sheet1  # Replace with your sheet name
            
            # Retrieve the existing scores from the Google Sheet
            existing_scores = score_sheet.get_all_records()
            score_dict = {row['User']: int(row['Score']) for row in existing_scores}
            
            # Update scores in the dictionary
            for user, score in self.user_scores.items():
                if user in score_dict:
                    if score > score_dict[user]:
                        score_dict[user] = score
                    elif score < score_dict[user]:
                        score_dict[user] += score
                else:
                    score_dict[user] = score

            # Clear the existing data in the Google Sheet
            score_sheet.clear()
            
            # Write the updated scores to the Google Sheet
            updated_scores = [['User', 'Score']]
            for user, score in score_dict.items():
                updated_scores.append([user, score])
            score_sheet.update(updated_scores)
            
            # Update the scores dictionary with the updated scores
            self.user_scores = score_dict
            await ctx.send('Scores Saved!')
        else:
            await ctx.send("Sorry, only mods and the channel owner can run this command.")


    @commands.command(name='Top10')
    async def top10_command(self, ctx: commands.Context):
        sorted_users = sorted(self.user_scores.items(), key=lambda x: x[1], reverse=True)[:10]
        response = "Top 10 Users: \n"
        for i, (user, score) in enumerate(sorted_users):
            response += f" {i+1}. {user}:  {score} points|\n"
        await ctx.send(response) 

    @commands.command(name='Hint')
    async def hint_command(self, ctx: commands.Context):
        global currentAnswer
        hint = ''
        for char in currentAnswer:
            if char == ' ':
                hint += ' '
            else:
                if random.random() <= 0.5:
                    hint += '_'
                else:
                    hint += char
        await ctx.send(f"The hint for the answer is: {hint}")


bot = Bot()
bot.run()
