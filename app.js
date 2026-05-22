const DEFAULT_SEARCH = "";

const state = {
  user: null,
  results: [],
  playlists: [],
  activePlaylistId: "",
  queue: [],
  history: [],
  currentTrack: null,
  currentList: [],
  currentIndex: -1,
};

const els = {
  audio: document.querySelector("#audioPlayer"),
  searchInput: document.querySelector("#searchInput"),
  searchButton: document.querySelector("#searchButton"),
  statusText: document.querySelector("#statusText"),
  resultsGrid: document.querySelector("#resultsGrid"),
  playlistGrid: document.querySelector("#playlistGrid"),
  playlistTabs: document.querySelector("#playlistTabs"),
  playlistForm: document.querySelector("#playlistForm"),
  playlistNameInput: document.querySelector("#playlistNameInput"),
  activePlaylistName: document.querySelector("#activePlaylistName"),
  deletePlaylist: document.querySelector("#deletePlaylist"),
  queueGrid: document.querySelector("#queueGrid"),
  playlistCount: document.querySelector("#playlistCount"),
  playerArt: document.querySelector("#playerArt"),
  playerTitle: document.querySelector("#playerTitle"),
  playerArtist: document.querySelector("#playerArtist"),
  playButton: document.querySelector("#playButton"),
  prevButton: document.querySelector("#prevButton"),
  nextButton: document.querySelector("#nextButton"),
  progress: document.querySelector("#progress"),
  currentTime: document.querySelector("#currentTime"),
  duration: document.querySelector("#duration"),
  userAvatar: document.querySelector("#userAvatar"),
  userName: document.querySelector("#userName"),
  userEmail: document.querySelector("#userEmail"),
  logoutButton: document.querySelector("#logoutButton"),
  demoLogin: document.querySelector("#demoLogin"),
  googleLogin: document.querySelector("#googleLogin"),
  clearQueue: document.querySelector("#clearQueue"),
  template: document.querySelector("#trackTemplate"),
};

function normalize(value) {
  return value.toLowerCase().trim().replace(/\s+/g, " ");
}

function userKey(part) {
  return `road-music:${state.user?.email || "guest"}:${part}`;
}

function makeId(prefix) {
  return `${prefix}:${Date.now()}:${Math.random().toString(16).slice(2)}`;
}

function defaultPlaylists() {
  return [{ id: "liked", name: "Liked Songs", tracks: [] }];
}

function saveLibrary() {
  localStorage.setItem(userKey("playlists"), JSON.stringify(state.playlists));
  localStorage.setItem(userKey("active-playlist"), state.activePlaylistId);
  localStorage.setItem(userKey("queue"), JSON.stringify(state.queue));
  updatePlaylistCount();
}

function loadLibrary() {
  state.playlists = readStoredArray(userKey("playlists"));
  if (!state.playlists.length) state.playlists = defaultPlaylists();
  state.activePlaylistId = localStorage.getItem(userKey("active-playlist")) || state.playlists[0].id;
  if (!getActivePlaylist()) state.activePlaylistId = state.playlists[0].id;
  state.queue = readStoredArray(userKey("queue"));
  renderPlaylists();
  renderQueue();
  saveLibrary();
}

function readStoredArray(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

function getActivePlaylist() {
  return state.playlists.find((playlist) => playlist.id === state.activePlaylistId);
}

function updatePlaylistCount() {
  const total = state.playlists.reduce((sum, playlist) => sum + playlist.tracks.length, 0);
  els.playlistCount.textContent = total;
}

function setUser(user) {
  state.user = user;
  els.userName.textContent = user.name;
  els.userEmail.textContent = user.email;
  els.logoutButton.hidden = false;
  els.demoLogin.hidden = true;
  els.googleLogin.hidden = true;

  if (user.picture) {
    els.userAvatar.innerHTML = `<img src="${user.picture}" alt="">`;
  } else {
    els.userAvatar.textContent = user.name.slice(0, 1).toUpperCase();
  }

  loadLibrary();
}

function setGuestUser() {
  state.user = null;
  els.userAvatar.textContent = "R";
  els.userName.textContent = "Guest listener";
  els.userEmail.textContent = "Sign in to save playlists";
  els.logoutButton.hidden = true;
  els.demoLogin.hidden = false;
  els.googleLogin.hidden = false;
  loadLibrary();
}

async function restoreUser() {
  try {
    const response = await fetch("/api/me");
    const data = await response.json();
    if (data.user?.email) setUser(data.user);
    else setGuestUser();
  } catch {
    setGuestUser();
  }
}

async function searchSongs(query) {
  const term = normalize(query || DEFAULT_SEARCH);

  els.statusText.textContent = term ? `Searching for "${term}"...` : "Loading all songs...";
  els.resultsGrid.innerHTML = "";

  try {
    const response = await fetch(`/api/songs?q=${encodeURIComponent(term)}`);
    if (!response.ok) throw new Error("Search failed");
    const data = await response.json();
    state.results = data.songs || [];
    renderTrackGrid(
      els.resultsGrid,
      state.results,
      "No full songs found in the cloud catalog. Add songs to songs.json or your cloud storage catalog."
    );
    els.statusText.textContent = `${state.results.length} full song${state.results.length === 1 ? "" : "s"} found.`;
  } catch {
    els.statusText.textContent = "Could not reach the Road-Music catalog.";
  }
}

function artworkFor(track) {
  if (track.artwork) return track.artwork;
  return `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 300'%3E%3Cdefs%3E%3ClinearGradient id='disc' x1='36' y1='264' x2='264' y2='36' gradientUnits='userSpaceOnUse'%3E%3Cstop stop-color='%23ff4c81'/%3E%3Cstop offset='.33' stop-color='%23ff9365'/%3E%3Cstop offset='.62' stop-color='%2367a7ff'/%3E%3Cstop offset='1' stop-color='%2338f2f5'/%3E%3C/linearGradient%3E%3Cfilter id='glow'%3E%3CfeGaussianBlur stdDeviation='5' result='b'/%3E%3CfeMerge%3E%3CfeMergeNode in='b'/%3E%3CfeMergeNode in='SourceGraphic'/%3E%3C/feMerge%3E%3C/filter%3E%3C/defs%3E%3Crect width='300' height='300' fill='%230d1117'/%3E%3Ccircle cx='150' cy='150' r='116' fill='%23111620' stroke='%2338f2f5' stroke-opacity='.28' stroke-width='5'/%3E%3Cpath d='M59 182c49-58 113-84 190-76-13 19-29 38-47 56-41 41-88 68-143 81 0 0-9-32 0-61Z' fill='url(%23disc)' opacity='.95'/%3E%3Cpath d='M64 205c57-10 110-39 158-88M76 225c60-13 112-42 157-91M93 242c55-17 101-44 140-82M52 177c44-52 102-80 174-85' fill='none' stroke='%23fff8da' stroke-width='5' stroke-linecap='round' opacity='.64'/%3E%3Ccircle cx='150' cy='150' r='58' fill='%23111620' stroke='%23fff8da' stroke-width='5' opacity='.92'/%3E%3Ccircle cx='150' cy='150' r='25' fill='none' stroke='%2338f2f5' stroke-width='4' opacity='.85'/%3E%3Cpath d='M176 68v113a37 37 0 1 1-20-33V84c0-14 15-23 27-16l45 26c18 10 20 36 3 49l-28 21v-32l17-13c5-4 4-12-2-15l-42-24Z' fill='%23fff2a8' filter='url(%23glow)'/%3E%3Ccircle cx='121' cy='178' r='31' fill='%23ff4c81'/%3E%3C/svg%3E`;
}

function renderTrackGrid(container, tracks, emptyMessage) {
  container.innerHTML = "";
  if (!tracks.length) {
    container.innerHTML = `<div class="empty-state">${emptyMessage}</div>`;
    return;
  }

  tracks.forEach((track, index) => {
    const node = els.template.content.firstElementChild.cloneNode(true);
    node.querySelector(".track-art").src = artworkFor(track);
    node.querySelector(".track-art").alt = `${track.title} cover`;
    node.querySelector("h4").textContent = track.title;
    node.querySelector("p").textContent = `${track.artist}${track.album ? ` - ${track.album}` : ""}`;
    node.querySelector(".art-button").addEventListener("click", () => playTrack(track, tracks, index));
    node.querySelector(".save-button").addEventListener("click", () => addToActivePlaylist(track));
    node.querySelector(".queue-button").addEventListener("click", () => addToQueue(track));
    container.appendChild(node);
  });
}

function renderPlaylists() {
  els.playlistTabs.innerHTML = "";
  state.playlists.forEach((playlist) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `playlist-tab${playlist.id === state.activePlaylistId ? " active" : ""}`;
    button.textContent = `${playlist.name} (${playlist.tracks.length})`;
    button.addEventListener("click", () => {
      state.activePlaylistId = playlist.id;
      renderPlaylists();
      saveLibrary();
    });
    els.playlistTabs.appendChild(button);
  });

  const active = getActivePlaylist();
  els.activePlaylistName.textContent = active?.name || "Liked Songs";
  renderTrackGrid(
    els.playlistGrid,
    active?.tracks || [],
    "This playlist is empty. Search for a song and press Save."
  );
  updatePlaylistCount();
}

function createPlaylist(name) {
  const trimmed = name.trim();
  if (!trimmed) return;
  const playlist = { id: makeId("playlist"), name: trimmed, tracks: [] };
  state.playlists.push(playlist);
  state.activePlaylistId = playlist.id;
  els.playlistNameInput.value = "";
  renderPlaylists();
  saveLibrary();
}

function deleteActivePlaylist() {
  if (state.playlists.length === 1) {
    const active = getActivePlaylist();
    active.tracks = [];
  } else {
    state.playlists = state.playlists.filter((playlist) => playlist.id !== state.activePlaylistId);
    state.activePlaylistId = state.playlists[0].id;
  }
  renderPlaylists();
  saveLibrary();
}

function renderQueue() {
  renderTrackGrid(els.queueGrid, state.queue, "Your queue is empty. Search for a song and press Queue.");
}

function addToActivePlaylist(track) {
  if (!state.user) {
    els.statusText.textContent = "Sign in first so Road-Music knows which playlist to save.";
    return;
  }

  const active = getActivePlaylist();
  if (!active) return;

  if (!active.tracks.some((item) => item.id === track.id)) {
    active.tracks.unshift(track);
    els.statusText.textContent = `"${track.title}" saved to ${active.name}.`;
    renderPlaylists();
    saveLibrary();
  } else {
    els.statusText.textContent = `"${track.title}" is already in ${active.name}.`;
  }
}

function addToQueue(track) {
  state.queue.push(track);
  renderQueue();
  saveLibrary();
  els.statusText.textContent = `"${track.title}" added to queue.`;
}

async function playTrack(track, list = state.results, index = 0) {
  if (!track.audioUrl) {
    els.statusText.textContent = "This song does not have an audio URL in the catalog.";
    return;
  }

  if (state.currentTrack) state.history.push(state.currentTrack);
  state.currentTrack = track;
  state.currentList = list;
  state.currentIndex = index;
  els.audio.src = track.audioUrl;

  try {
    await els.audio.play();
    updatePlayer(track);
  } catch {
    els.statusText.textContent = "The browser could not play this song URL. Check cloud CORS/public access.";
  }
}

function updatePlayer(track) {
  els.playerTitle.textContent = track.title;
  els.playerArtist.textContent = track.artist;
  els.playerArt.src = artworkFor(track);
  els.playerArt.hidden = false;
  els.playButton.textContent = "Pause";
}

function playNext() {
  if (state.queue.length) {
    const [nextTrack] = state.queue.splice(0, 1);
    renderQueue();
    saveLibrary();
    playTrack(nextTrack, state.queue, 0);
    return;
  }

  if (state.currentList.length && state.currentIndex < state.currentList.length - 1) {
    playTrack(state.currentList[state.currentIndex + 1], state.currentList, state.currentIndex + 1);
  }
}

function playPrevious() {
  if (state.history.length) {
    const previousTrack = state.history.pop();
    playTrack(previousTrack, state.currentList, state.currentIndex);
  }
}

function togglePlay() {
  if (!state.currentTrack && state.results.length) {
    playTrack(state.results[0], state.results, 0);
    return;
  }

  if (els.audio.paused) {
    els.audio.play();
    els.playButton.textContent = "Pause";
  } else {
    els.audio.pause();
    els.playButton.textContent = "Play";
  }
}

function formatTime(seconds) {
  if (!Number.isFinite(seconds)) return "0:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
}

function showView(viewId, button) {
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active-view"));
  document.querySelector(`#${viewId}`).classList.add("active-view");
  document.querySelectorAll(".nav-button").forEach((nav) => nav.classList.remove("active"));
  button.classList.add("active");
}

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function wireEvents() {
  els.searchButton.addEventListener("click", () => searchSongs(els.searchInput.value));
  els.searchInput.addEventListener("input", debounce(() => searchSongs(els.searchInput.value), 320));
  els.searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") searchSongs(els.searchInput.value);
  });

  els.playlistForm.addEventListener("submit", (event) => {
    event.preventDefault();
    createPlaylist(els.playlistNameInput.value);
  });
  els.deletePlaylist.addEventListener("click", deleteActivePlaylist);

  els.playButton.addEventListener("click", togglePlay);
  els.nextButton.addEventListener("click", playNext);
  els.prevButton.addEventListener("click", playPrevious);

  els.audio.addEventListener("timeupdate", () => {
    const percent = els.audio.duration ? (els.audio.currentTime / els.audio.duration) * 100 : 0;
    els.progress.value = String(percent);
    els.currentTime.textContent = formatTime(els.audio.currentTime);
    els.duration.textContent = formatTime(els.audio.duration);
  });
  els.audio.addEventListener("ended", playNext);
  els.audio.addEventListener("pause", () => {
    els.playButton.textContent = "Play";
  });
  els.audio.addEventListener("play", () => {
    els.playButton.textContent = "Pause";
  });
  els.progress.addEventListener("input", () => {
    if (els.audio.duration) {
      els.audio.currentTime = (Number(els.progress.value) / 100) * els.audio.duration;
    }
  });

  document.querySelectorAll(".nav-button").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.view, button));
  });

  els.demoLogin.addEventListener("click", () => {
    setUser({ name: "Google Demo User", email: "demo.user@gmail.com", picture: "" });
  });

  els.logoutButton.addEventListener("click", () => {
    window.location.href = "/auth/logout";
  });
  els.clearQueue.addEventListener("click", () => {
    state.queue = [];
    renderQueue();
    saveLibrary();
  });
}

window.addEventListener("load", () => {
  wireEvents();
  restoreUser();
  searchSongs(DEFAULT_SEARCH);
});
