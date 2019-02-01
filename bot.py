import discord, BTEdb, traceback, sys, time, json, requests, asyncio
from fuzzywuzzy import fuzz
sys.path.append(".")
from gyms import gyms, hardcodes

#server = 415924072640151555 # nrv pkgo
#server = 498691390683742208 # pixel
cats = [
      492754071468638234 # nrv pkgo raids
    , 539177781351809047 # nrv pkgo raids tier5
    ]
#cat = 498691390683742209 # pixel text channels
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
    gym = gym.lower().replace("'", "").strip()
    if gym in hardcodes: gym = hardcodes[gym]
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

# sometimes fails
def parse_time(when):
    if "!timerset" in when: return False
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
    print("Submitted to server with " + str(r.status_code))
    if r.status_code not in [200, 300, 301, 302, 303]:
        raise RuntimeError("Failed to send request: " + r.url)

def update_all():
    for obj in db.Dump("master"):
        if parse_time(obj["when"]) < 0 and obj["state"] != "hatched":
            continue
        update_server(obj)

def update_db(obj):
    if not parse_time(obj["when"]):
        return
    if obj["state"] == "dead":
        db.Delete("master", id = obj["id"])
        return
    existing = db.Select("master", id = obj["id"])
    if len(existing) == 0:
        db.Insert("master", **obj);
        update_server(obj)
    else:
        existing = existing[0]
        # sometimes the initial "when" reads as "Set with !timerset", and so we want to update the database when that data is available
        if existing["state"] != obj["state"] or existing["raid"] != obj["raid"] or existing["when"] != obj["when"]:
            if existing["state"] == "egg" and obj["state"] == "hatched":
                obj["raid"] = "Hatched " + obj["raid"]
            db.Update("master", [existing], **obj)
            update_server(obj)

def clean_db(channels):
    alive = set([channel.id for channel in channels])
    dead = set()
    for row in db.Dump("master"):
        if not row["id"] in alive:
            dead.add(row["id"])
    db.Delete("master", lambda r: r["id"] in dead)
    print("Deleted " + str(len(dead)) + " dead objects from the database")


def extract_fields(message):
    if len(message.embeds) == 0: return {}
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
    return fields


class MyClient(discord.Client):
    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))
        #await self.check()

    async def check_channel_real(self, channel):
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
                if split[i] == "Meowth!":
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
            fields = extract_fields(message)
            when = fields["Expires:"] if "Expires:" in fields else fields["Hatches:"]
            raidobj = {"raid": raid, "location": location, "gym": gym, "fields": fields, "state": state, "when": when, "id": channel.id}
            print(json.dumps(raidobj, indent = 4))
            update_db(raidobj)
            break

    async def send_to_user(self, user, text):
        user = self.get_user(user)
        if user.dm_channel is None:
            await user.create_dm()
        await user.dm_channel.send(content = text)
    
    async def check_channel(self, channel):
        try:
            await self.check_channel_real(channel)
        except:
            await self.send_to_user(me, "ERROR: ```\n" + traceback.format_exc() + "\n```")

    async def check(self, channels):
        for channel in channels:
            if channel.category and channel.category.id in cats:
                await self.check_channel(channel)
        print("Check completed")

    async def on_message(self, message):
        print('Message from {0.author.name} ({0.author.id}) in {0.guild.id}, bot? {0.author.bot}: {0.content}'.format(message))
        if message.content == "!!!check-all"and message.author.id == me:
            print("Checking")
            await self.check(message.guild.channels)
        if message.content == "!!!check" and message.author.id == me:
            print("Checking")
            await self.check_channel(message.channel)
        if message.content == "!!!clean" and message.author.id == me:
            print("Cleaning")
            clean_db(message.guild.channels)
        if message.content == "!!!dump":
            result = db.Select("master", id = message.channel.id)
            if len(result) == 0:
                await self.send_to_user(message.author.id, "No data in the database for channel " + str(message.channel.id))
            else:
                await self.send_to_user(message.author.id, "```json\n" + json.dumps(result[0], indent = 4) + "\n```")
        if message.content.startswith("!!!location-test "):
            location = " ".join(message.content.split()[1:])
            await self.send_to_user(message.author.id, "Location `" + location + "` resolves to gym `" + best_guess(location) + "`")
        if message.content == "!!!force-update" and message.author.id == me:
            update_all();
        if message.author.id == meowth and message.channel.category and message.channel.category.id in cats:
            if message.content.startswith("This egg will hatch") or message.content.strip() == "":
                print("discarding new message")
                return
            print("Caught meowth-sent message in #" + message.channel.name)
            await asyncio.sleep(1)
            await self.check_channel(message.channel)

    async def on_message_edit(self, before, after):
        if before.author.id == meowth and before.channel.category and before.channel.category.id in cats:
            if before.content == after.content and extract_fields(before) == extract_fields(after):
                print("discarding edit")
                return
            print("Caught meowth-edited message in #" + before.channel.name)
            await asyncio.sleep(1)
            await self.check_channel(before.channel)

client = MyClient()
client.run('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX')
