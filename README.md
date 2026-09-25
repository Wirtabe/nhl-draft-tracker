# NHL Draft Tracker

Valmis pohja kaveriporukan NHL-draftin pisteiden seurantaan.

## Arkkitehtuuri

- `data/draft.json` = varatut pelaajat
- `scripts/update_stats.py` = hakee NHL:n Stats REST API:sta kauden G+A-pisteet
- `public/data.json` = julkaistava laskettu data
- `public/index.html` + CSS + JS = raportti
- `.github/workflows/update.yml` = päivittää pisteet noin 30 min välein
- `.github/workflows/deploy.yml` = julkaisee `public/`-kansion GitHub Pagesiin

Pisteet ovat **maalit + syötöt**.

## 1. Luo repository

Luo GitHubiin repository esimerkiksi nimellä `nhl-draft-tracker`.

GitHub Free -tilillä GitHub Pagesia varten repositoryn pitää olla public. Älä lisää repositoryyn mitään salaista.

## 2. Kopioi tiedostot

Kopioi kaikki tämän projektin tiedostot repositoryn juureen ja pushaa `main`-branchiin.

## 3. Muokkaa draftia

Avaa `data/draft.json`.

Lisää omat joukkueet ja pelaajat:

```json
{
  "name": "Connor McDavid",
  "nhl_id": 8478402
}
```

Käytä mieluiten NHL:n omaa numeric player ID:tä.

## 4. Ota Pages käyttöön

GitHubissa:

**Repository → Settings → Pages → Build and deployment → Source → GitHub Actions**

Tämän jälkeen `deploy.yml` julkaisee `public/`-kansion Pages-sivuksi.

GitHubin Pages-dokumentaatio:
https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site

## 5. Käynnistä ensimmäinen päivitys

Avaa:

**Actions → Update NHL stats → Run workflow**

Workflow:

1. hakee pelaajien kauden tilastot
2. laskee joukkueiden pisteet
3. kirjoittaa `public/data.json`
4. committaa muuttuneen datan takaisin repositoryyn

`public/data.json`-muutos käynnistää tämän jälkeen Pages-deployn.

## 6. Raportin osoite

GitHub Pagesin URL on yleensä:

`https://KÄYTTÄJÄNIMI.github.io/nhl-draft-tracker/`

Anna kavereille tämä osoite.

## Päivitystiheys

`update.yml` ajaa noin 30 minuutin välein sekä aina, kun `data/draft.json` muuttuu.

GitHubin scheduled workflow -ajoissa voi olla viivettä, joten "30 min välein" ei tarkoita tarkkaa kellonaikaa.

## NHL API

Pisteiden lähteenä käytetään NHL Stats REST API:n skater summary -endpointia ja suodatetaan `playerId`, `seasonId` ja `gameTypeId` -kentillä.

Nykyinen ratkaisu on tarkoitettu tavallisille NHL:n kenttäpelaajille. Jos haluatte myöhemmin maalivahteja tai oman pisteytyksen, laskentaan voidaan lisätä erillinen sääntö.

## Jos haluat yksityisen repositoryn

Tämä ratkaisu olettaa GitHub Free + public repository -mallin. GitHub Pages -sivusto itsessään on julkinen.

Jos draftin sisältö ei saa näkyä repositoryssa, älä käytä tätä public-repository-ratkaisua sellaisenaan. Silloin kannattaa erottaa private data/laskenta ja julkinen raporttisivu.
