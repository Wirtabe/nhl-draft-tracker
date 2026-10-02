# NHL Draft Tracker

Tämä versio hakee NHL-pelaajien tehopisteet automaattisesti, vaikka
`data/draft.json` sisältäisi aluksi vain pelaajan nimen, varausnumeron ja
pelipaikan.

## Datarakenne

`data/draft.json` on nyt lähdedata, jota muokataan käsin.

Esimerkki:

```json
{
  "season": "2026-2027",
  "game_type": 2,
  "teams": [
    {
      "coach": "Riku",
      "name": "Söhlöt",
      "players": [
        {
          "draft_number": 1,
          "name": "Nathan MacKinnon",
          "position": "H"
        }
      ]
    }
  ]
}
```

Pelipaikat:

- `H` = hyökkääjä
- `P` = puolustaja
- `M` = maalivahti

## Miten automaattinen päivitys toimii?

`scripts/update_stats.py` tekee neljä asiaa:

1. hakee pelaajan nimellä NHL:n player search -palvelusta NHL player ID:n
2. tallentaa löydetyn ID:n välimuistiin `data/player_ids.json`
3. hakee kauden skater- ja goalie-yhteenvedot NHL Stats REST API:sta
4. laskee `pisteet = maalit + syötöt` ja kirjoittaa tuloksen `public/data.json`

Ensimmäinen ajo tekee enemmän nimihakuja. Seuraavilla ajoilla pelaajien NHL-ID:t
ovat jo `data/player_ids.json`-tiedostossa, joten tilastopäivitys tarvitsee
normaalisti vain kauden tilastopyynnöt.

Maalivahtien tehopisteet lasketaan samalla tavalla heidän goalie summary
-rivinsä `goals + assists` -kentistä.

## GitHub Actions

`.github/workflows/update.yml`:

- ajetaan noin 30 minuutin välein
- voidaan ajaa käsin Actions-välilehdeltä
- käynnistyy myös, jos draftia, overrideja tai päivitysskriptiä muokataan
- committaa takaisin:
  - `public/data.json`
  - `data/player_ids.json`

`public/data.json`-muutos käynnistää Pages-deployn nykyisen `deploy.yml`:n kautta.

## Jos pelaajan nimi ei tunnistu

Raportissa pelaajan kohdalla näkyy:

`NHL-pelaajaa ei tunnistettu`

Voit korjata haun `data/player_overrides.json`-tiedostossa.

Esimerkki oikeinkirjoituksen korjauksesta:

```json
{
  "Excelissä oleva nimi": {
    "search_name": "NHL:n käyttämä nimi"
  }
}
```

Tai jos tiedät NHL player ID:n:

```json
{
  "Excelissä oleva nimi": {
    "nhl_id": 8478402
  }
}
```

Tämän jälkeen commitoi muutos. Update-workflow käynnistyy automaattisesti.

## Tärkeää

Älä enää käytä `public/data.json`-tiedostoa draftin käsin muokkaamiseen.
Se on generoitu raporttitiedosto ja GitHub Actions korvaa sen.

Muokkaa jatkossa:

`data/draft.json`

## Ensimmäinen käyttöönotto

Kun olet puskenut tämän version repositoryyn:

1. Avaa GitHub → Actions
2. Avaa `Update NHL stats`
3. Valitse `Run workflow`
4. Odota ajon valmistumista
5. Tarkista mahdolliset `Warnings` ajon lokista
6. `Deploy NHL report to GitHub Pages` julkaisee syntyneen `public/data.json`:n

Jos kaikki pelaajat tunnistuvat, `public/data.json`:ssa näkyy
`"api_status": "ok"`.


## v6: maalivahtien pisteytys

Pisteytys on nyt:

- Hyökkääjä (`H`): maalit + syötöt
- Puolustaja (`P`): maalit + syötöt
- Maalivahti (`M`): `voitot × 2 + nollapelit × 2 + maalit + syötöt`

Esimerkki maalivahdille:

- 12 voittoa
- 3 nollapeliä
- 0 maalia
- 2 syöttöä

Pisteet = `12×2 + 3×2 + 0 + 2 = 32`.

`public/data.json` sisältää maalivahdeille myös kentät `wins` ja `shutouts`.


## v7: pisteet NHL Web API:n game logista

Kenttäpelaajien pisteet haetaan nyt pelaajakohtaisesta endpointista:

`/v1/player/{playerId}/game-log/{season}/{gameType}`

Kauden maalit ja syötöt summataan ottelulokista, joten juuri päättyneen ottelun
tilasto ei ole riippuvainen hitaammin päivittyvästä season summary -taulusta.

Maalivahdeille:
- voitot lasketaan game login `decision == "W"` -riveistä
- nollapelit otetaan game login mahdollisesta shutout-kentästä; jos sitä ei ole,
  nollapeli johdetaan konservatiivisesti 0 päästetystä maalista ja vähintään
  58 minuutin peliajasta
- maalivahdin harvinaiset maalit ja syötöt täydennetään goalie summary -datasta

Maalivahtien fantasypisteet ovat edelleen:

`voitot × 2 + nollapelit × 2 + maalit + syötöt`

GitHub Actionsin `Show update summary` tulostaa lisäksi Jack Hughesin
diagnostiikkarivin, jotta game-log-päivityksen toiminta on helppo varmistaa.
