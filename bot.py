import discord, BTEdb, traceback, sys, time, json, requests
from fuzzywuzzy import fuzz
sys.path.append(".")
from gyms import gyms

#server = 415924072640151555 # nrv pkgo
#server = 498691390683742208 # pixel
cat = 492754071468638234 # nrv pkgo raids
cat = 498691390683742209 # pixel text channels
ignores = [
      498691390683742210 # pixel general
    , 538418204398190594 # pixel test2
    , 520296127476531226 # nrv pkgo raid command guide
    , 415924408327077888 # nrv pkgo raid report
    ]
meowth = 346759953006198784 # hope this is the same

me = 158673755105787904

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

def parse_time(when):
    now = time.localtime()
    now = now.tm_hour * 60 + now.tm_min
    when = when.split("(")[1].split(")")[0].split(":") # poor man's regular expression
    when = int(when[0]) * 60 + int(when[1])
    return when - now

def update_server(obj):
    gym_id = gyms[obj["gym"]]
    timestamp = time.strftime('%Y%m%dT%H%M%S', time.localtime())
    raid_boss = obj["raid"]
    timer_minutes = parse_time(obj["when"])
    timer_type = "Egg Hatch" if obj["state"] in ["egg", "hatched"] else "Raid End"
    r = requests.post("http://hh-club.com/AddRaid_submit.php", data = {
          "Gym_ID": gym_id
        , "Timestamp": timestamp
        , "RaidBoss": raid_boss
        , "Timer_minutes": timer_minutes
        , "TimerType": timer_type
    })
    print(r.status_code)
    if r.status_code not in [200, 300, 301, 302, 303]:
        raise RuntimeError("Failed to send request: " + r.url)

def update_all():
    for obj in db.Dump("master"):
        if parse_time(obj["when"]) < 0 and obj["state"] != "hatched":
            continue
        update_server(obj)

def update_db(obj):
    if obj["state"] == "dead":
        db.Delete("master", id = obj["id"])
        return
    existing = db.Select("master", id = obj["id"])
    if len(existing) == 0:
        db.Insert("master", **obj);
        update_server(obj)
    else:
        existing = existing[0]
        if existing["state"] != obj["state"] or existing["raid"] != obj["raid"]:
            if existing["state"] == "egg" and obj["state"] == "hatched":
                obj["raid"] = "Hatched " + obj["raid"]
            db.Update("master", [existing], **obj)
            update_server(obj)


class MyClient(discord.Client):
    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))
        #await self.check()

    async def check_channel(self, channel):
        if channel.id in ignores: return
        #print(channel.id)
        #print(channel.created_at)
        #async for message in channel.history(around = channel.created_at, reverse = True, limit = 10):
        state = False
        print("Awaiting pins")
        for message in await channel.pins():
            print("Got pins")
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
            state = "dead" if channel.name.startswith("expired-") else ("hatched" if channel.name.startswith("hatched-") else ("egg" if egg else "raid"))
            location = " ".join(location)[:-1]
            gym = best_guess(location)
            raid = " ".join(raid)
            fields = {}
            lastfield = False
            for field in message.embeds[0].fields:
                name = field.name.replace("*", "")
                value = field.value.replace("*", "")
                if name == "\u200b":
                    name = lastname
                if name in fields:
                    fields[name] += " " + value
                else:
                    fields[name] = value
                lastname = name
            when = fields["Expires:"] if "Expires:" in fields else fields["Hatches:"]
            #minutes_left = parse_time(unparsed_time) # may be negative # TODO move this line to update_server
            raidobj = {"raid": raid, "location": location, "gym": gym, "fields": fields, "state": state, "when": when, "id": channel.id}
            print(json.dumps(raidobj, indent = 4))
            update_db(raidobj)
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
        #print('Message from {0.author.name} ({0.author.id}) in {0.guild.id}, bot? {0.author.bot}: {0.content}'.format(message))
        if message.content == "!!!check":
            print("Checking")
            await self.check(message.guild.channels)
        if message.content == "!!!force-update":
            update_all();
        if message.author.id == meowth:
            print("Caught meowth-sent message in #" + message.channel.name)
            await self.check_channel(message.channel)

    async def on_message_edit(self, before, after):
        if before.author.id == meowth:
            print("Caught meowth-edited message in #" + before.channel.name)
            await self.check_channel(before.channel)

client = MyClient()
client.run('NTM4NDAwOTA2Nzc4MTE2MDk5.DyzRBg.3xSJdAk_oR6g46eUI6j_oO00Q8M')

