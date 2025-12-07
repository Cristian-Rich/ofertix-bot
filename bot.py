import os
import discord
from discord.ext import commands
import requests
from bs4 import BeautifulSoup
import random
import datetime
import json

TOKEN = os.getenv("TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
shown_games = set()
last_reset_date = None

DATA_FILE = "shown_games.json"

def load_shown_games():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        today = str(datetime.date.today())
        if data.get("date") == today:
            # transforma em set de tuplas (store, name)
            return set((g["store"], g["name"]) for g in data.get("games", [])), today
    return set(), str(datetime.date.today())


def save_shown_games(shown_games, date):
    data = {"date": date, "games": [{"store": s, "name": n} for (s, n) in shown_games]}
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)



shown_games, last_reset_date = load_shown_games()

def reset_daily():
    global shown_games, last_reset_date
    today = str(datetime.date.today())
    if last_reset_date != today:
        shown_games = set()
        last_reset_date = today
        save_shown_games(shown_games, last_reset_date)


# Funções para !ofertas 

def get_steam_deals():
    reset_daily()

    url = "https://store.steampowered.com/search/?specials=1&cc=br&l=pt-BR"
    r = requests.get(url, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")

    deals = []
    for row in soup.select(".search_result_row"):
        name = row.select_one(".title").get_text(strip=True)
        link = row["href"]

        if ("steam", name) in shown_games:
            continue  

        r2 = requests.get(link, timeout=20)
        soup2 = BeautifulSoup(r2.text, "html.parser")
        discount_el = soup2.select_one(".discount_block .discount_pct")
        discount = discount_el.get_text(strip=True) if discount_el else "Sem desconto"
        price_el = soup2.select_one(".discount_block .discount_final_price")
        price = price_el.get_text(strip=True) if price_el else "Preço indisponível"

        deals.append({
            "name": name,
            "discount": discount,
            "price_fmt": price,
            "url": link
        })
        shown_games.add(("steam", name))

        if len(deals) == 5:
            break

    save_shown_games(shown_games, last_reset_date)
    return deals


def get_epic_free_games():
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
    r = requests.get(url, timeout=15).json()
    games = []
    for g in r["data"]["Catalog"]["searchStore"]["elements"]:
        if g.get("price", {}).get("totalPrice", {}).get("discountPrice") == 0:
            slug = g.get("productSlug") or g.get("urlSlug")
            if not slug:
                mappings = g.get("catalogNs", {}).get("mappings", [])
                if mappings:
                    slug = mappings[0].get("pageSlug")
            epic_url = f"https://store.epicgames.com/pt-BR/p/{slug}" if slug else "https://store.epicgames.com/pt-BR/free-games"
            games.append({"name": g.get("title", "Jogo"), "url": epic_url})
    return games

def get_nuuvem_deals(max_pages=5):
    reset_daily()
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "pt-BR"}
    deals = []

    for page in range(1, max_pages+1):
        url = f"https://www.nuuvem.com/br-pt/catalog/platforms/pc/price/promo/types/games/sort/bestselling/sort-mode/desc?page={page}"
        r = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        for card in soup.select("article.game-card"):
            name = card.select_one(".game-card__product-name").get_text(strip=True)
            link = card.find_parent("a")["href"]
            discount_el = card.select_one(".product-price--discount")
            discount = discount_el.get_text(strip=True) if discount_el else "Sem desconto"
            int_el = card.select_one(".product-price--val .integer")
            dec_el = card.select_one(".product-price--val .decimal")
            price = f"R$ {int_el.get_text(strip=True)}{dec_el.get_text(strip=True)}" if int_el and dec_el else "Preço indisponível"

            if ("nuuvem", name) in shown_games:
                continue

            deals.append({"name": name, "discount": discount, "price": price, "url": link})
            shown_games.add(("nuuvem", name))

            if len(deals) == 5:
                save_shown_games(shown_games, last_reset_date)
                return deals

    save_shown_games(shown_games, last_reset_date)
    return deals

# Funções para !dica

def get_random_steam_game():
    # sorteia uma página de promoções da Steam
    page = random.randint(1, 10)
    url = f"https://store.steampowered.com/search/results/?specials=1&cc=br&l=pt-BR&page={page}"
    r = requests.get(url, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    rows = soup.select(".search_result_row")
    if not rows:
        return None

    row = random.choice(rows)
    name = row.select_one(".title").get_text(strip=True)
    link = row["href"]

    # acessa a página do jogo para pegar preço e desconto
    r2 = requests.get(link, timeout=20)
    soup2 = BeautifulSoup(r2.text, "html.parser")

    discount_el = soup2.select_one(".discount_block .discount_pct")
    discount = discount_el.get_text(strip=True) if discount_el else "Sem desconto"

    price_el = soup2.select_one(".discount_block .discount_final_price")
    price = price_el.get_text(strip=True) if price_el else "Preço indisponível"

    return {"name": name, "discount": discount, "price": price, "url": link}


def get_random_epic_game():
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
    r = requests.get(url, timeout=15).json()
    free_games = []
    for g in r["data"]["Catalog"]["searchStore"]["elements"]:
        if g.get("price", {}).get("totalPrice", {}).get("discountPrice") == 0:
            slug = g.get("productSlug") or g.get("urlSlug")
            if not slug:
                mappings = g.get("catalogNs", {}).get("mappings", [])
                if mappings:
                    slug = mappings[0].get("pageSlug")
            epic_url = f"https://store.epicgames.com/pt-BR/p/{slug}" if slug else "https://store.epicgames.com/pt-BR/free-games"
            free_games.append({"name": g.get("title", "Jogo"), "url": epic_url})
    return random.choice(free_games) if free_games else None

def get_random_nuuvem_game(max_pages=20):
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "pt-BR"}
    page = random.randint(1, max_pages)
    url = f"https://www.nuuvem.com/br-pt/catalog/platforms/pc/price/promo/types/games/sort/bestselling/sort-mode/desc?page={page}"
    r = requests.get(url, headers=headers, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    cards = soup.select("article.game-card")
    if not cards:
        return None
    card = random.choice(cards)
    name = card.select_one(".game-card__product-name").get_text(strip=True)
    link = card.find_parent("a")["href"]
    discount_el = card.select_one(".product-price--discount")
    discount = discount_el.get_text(strip=True) if discount_el else "Sem desconto"
    int_el = card.select_one(".product-price--val .integer")
    dec_el = card.select_one(".product-price--val .decimal")
    price = f"R$ {int_el.get_text(strip=True)}{dec_el.get_text(strip=True)}" if int_el and dec_el else "Preço indisponível"
    return {"name": name, "discount": discount, "price": price, "url": link}


@bot.command()
async def ofertas(ctx):
    steam = get_steam_deals()
    epic = get_epic_free_games()
    nuuvem = get_nuuvem_deals()

    embed = discord.Embed(title="🎮 Promoções e Jogos Grátis", color=0x2ecc71)
    for s in steam:
        embed.add_field(name=f"{s['name']} ({s['discount']})",
                        value=f"{s['price_fmt']} → {s['url']}", inline=False)
    for e in epic:
        embed.add_field(name=f"{e['name']} (GRÁTIS na Epic)",
                        value=e['url'], inline=False)
    for n in nuuvem:
        embed.add_field(name=f"{n['name']} ({n['discount']})",
                        value=f"{n['price']} → {n['url']}", inline=False)

    await ctx.send(embed=embed)

@bot.command()
async def dica(ctx):
    loja = random.choice(["steam", "nuuvem"])

    if loja == "steam":
        game = get_random_steam_game()
        if game:
            embed = discord.Embed(
                title="🎲 Dica de Jogo (Steam)",
                description=f"**{game['name']}**\n{game['price']} ({game['discount']})\n{game['url']}",
                color=0x1b2838
            )
            await ctx.send(embed=embed)

    elif loja == "nuuvem":
        game = get_random_nuuvem_game(max_pages=20)
        if game:
            embed = discord.Embed(
                title="🎲 Dica de Jogo (Nuuvem)",
                description=f"**{game['name']}**\n{game['price']} ({game['discount']})\n{game['url']}",
                color=0x2ecc71
            )
            await ctx.send(embed=embed)
@bot.event
async def on_ready():
    print(f"Bot logado como {bot.user}")
    channel = bot.get_channel(CHANNEL_ID)

    steam = get_steam_deals()
    epic = get_epic_free_games()
    nuuvem = get_nuuvem_deals()

    embed = discord.Embed(title="🎮 Promoções e Jogos Grátis", color=0x2ecc71)
    for s in steam:
        embed.add_field(name=f"{s['name']} ({s['discount']})",
                        value=f"{s['price_fmt']} → {s['url']}", inline=False)
    for e in epic:
        embed.add_field(name=f"{e['name']} (GRÁTIS na Epic)",
                        value=e['url'], inline=False)
    for n in nuuvem:
        embed.add_field(name=f"{n['name']} ({n['discount']})",
                        value=f"{n['price']} → {n['url']}", inline=False)

    await channel.send(embed=embed)


bot.run(TOKEN)
