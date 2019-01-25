import discord, BTEdb, traceback, sys
from fuzzywuzzy import fuzz
sys.path.append(".")
from gyms import gyms
 
def distance(s1, s2):
    return 100 - fuzz.token_set_ratio(s1, s2)

def best_guess(gym):
    best = False
    best_dist = False
    for key in gyms.keys():
        dist = distance(gym, key)
        if not best or best_dist > dist:
            best = key
            best_dist = dist
    return best

db = BTEdb.Database("hhclub-bridge.json")

if not db.TableExists("master"):
    db.CreateTable("master")

#server = 415924072640151555 # nrv pkgo
#server = 498691390683742208 # pixel
cat = 492754071468638234 # nrv pkgo raids
#cat = 498691390683742209 # pixel text channels
meowth = 346759953006198784 # hope this is the same

me = 158673755105787904

class MyClient(discord.Client):
    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))

    async def check_channel(self, channel):
        #print(channel.id)
        #print(channel.created_at)
        #async for message in channel.history(around = channel.created_at, reverse = True, limit = 10):
        state = False
        for message in await channel.pins():
            if message.author.id != meowth: continue
            #print(message)
            split = message.content.split()
            raid = []
            location = []
            egg = None
            inraid = False
            inlocation = False
            for i in range(len(split)):
                if i == 0:
                    inraid = split[1] != "The"
                    continue # skip Meowth!
                if split[i] == "raid" or split[i] == "raid!":
                    inraid = False
                    egg = split[i + 1] == "egg"
                    continue
                if split[i] == "Details:":
                    inlocation = True
                    continue
                if split[i] == "a" and split[i - 1] == "into" and split[i - 2] == "hatched":
                    inraid = True
                    continue
                if split[i] == "Coordinate" and split[i + 1] == "here!":
                    break
                if inraid:
                    raid.append(split[i])
                if inlocation:
                    location.append(split[i])
            state = "dead" if channel.name.startswith("expired-") else ("egg" if egg else "raid")
            location = " ".join(location)[:-1]
            gym = best_guess(location)
            raid = " ".join(raid)
            fields = {}
            lastfield = False
            for field in message.embeds[0].fields:
                name = field.name
                if name == "\u200b":
                    name = lastname
                if name in fields:
                    fields[name] += " " + field.value
                else:
                    fields[name] = field.value
                lastname = name
            print(raid)
            print(location)
            print(gym)
            print(fields)
            print(state)
            print()
            break

    async def check(self, channels):
        for channel in channels:
            if channel.category and channel.category.id == cat:
                try:
                    await self.check_channel(channel)
                except:
                    print("ERROR: " + traceback.format_exc())
                    user = self.get_user(me)
                    if user.dm_channel is None:
                        await user.create_dm()
                    await user.dm_channel.send(content = "ERROR: ```" + traceback.format_exc() + "```")
        print("Check completed")

    async def on_message(self, message):
        print('Message from {0.author.name} ({0.author.id}) in {0.guild.id}, bot? {0.author.bot}: {0.content}'.format(message))
        if message.content == "!!!check":
            await self.check(message.guild.channels)

client = MyClient()
client.run('NTM4NDAwOTA2Nzc4MTE2MDk5.DyzRBg.3xSJdAk_oR6g46eUI6j_oO00Q8M')

