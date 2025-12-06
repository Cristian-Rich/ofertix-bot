import os
import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup

# Pegando o TOKEN e o CHANNEL_ID das variáveis de ambiente
TOKEN = os.getenv("TOKEN")          
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))  # ID do canal

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

def get_steam_deals():
    url = "https://store.steampowered.com/api/featured/"
    r = requests.get(url).json()
    deals = []
    for item in r.get("featured_win", []):
        if item.get("discount_percent", 0) > 0:
            deals.append({
                "name": item["name"],
                "discount": item["discount_percent"],
                "price": item["final_price"]/100,
                "url": f"https://store.steampowered.com/app/{item['id']}"
            })
    return deals[:5]

def get_epic_free_games():
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
    r = requests.get(url).json()
    games = []
    for game in r["data"]["Catalog"]["searchStore"]["elements"]:
        if game["price"]["totalPrice"]["discountPrice"] == 0:
            games.append({
                "name": game["title"],
                "url": f"https://store.epicgames.com/p/{game['productSlug']}"
            })
    return games

def get_nuuvem_deals():
    url = "https://www.nuuvem.com/catalog?filter[platform]=pc&sort=discount"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    deals = []
    for item in soup.select(".product-card--grid"):
        name = item.select_one(".product-title").get_text(strip=True)
        link = "https://www.nuuvem.com" + item.select_one("a")["href"]
        discount = item.select_one(".product-discount")
        price = item.select_one(".product-price--discounted")
        if discount and price:
            deals.append({
                "name": name,
                "discount": discount.get_text(strip=True),
                "price": price.get_text(strip=True),
                "url": link
            })
    return deals[:5]

@tasks.loop(hours=6)
async def post_deals():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return

    steam = get_steam_deals()
    epic = get_epic_free_games()
    nuuvem = get_nuuvem_deals()

    embed = discord.Embed(title="🎮 Promoções e Jogos Grátis", color=0x2ecc71)

    for s in steam:
        embed.add_field(
            name=f"{s['name']} (-{s['discount']}%)",
            value=f"R$ {s['price']:.2f} → {s['url']}",
            inline=False
        )

    for e in epic:
        embed.add_field(
            name=f"{e['name']} (GRÁTIS na Epic)",
            value=e['url'],
            inline=False
        )

    for n in nuuvem:
        embed.add_field(
            name=f"{n['name']} ({n['discount']})",
            value=f"{n['price']} → {n['url']}",
            inline=False
        )

    await channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logado como {bot.user}")
    post_deals.start()

bot.run(TOKEN)
