const DEFAULT_SEARCH = "";
const DEFAULT_TRACK_ART = "assets/default-track-avatar.png";
const PLAYING_CLASS = "is-playing";

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
  pendingSaveTrack: null,
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
  playlistNameError: document.querySelector("#playlistNameError"),
  activePlaylistName: document.querySelector("#activePlaylistName"),
  deletePlaylist: document.querySelector("#deletePlaylist"),
  confirmDeletePlaylist: document.querySelector("#confirmDeletePlaylist"),
  queueGrid: document.querySelector("#queueGrid"),
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
  sidebar: document.querySelector("#sidebar"),
  sidebarToggle: document.querySelector("#sidebarToggle"),
  openCreatePlaylist: document.querySelector("#openCreatePlaylist"),
  modalBackdrop: document.querySelector("#modalBackdrop"),
  playlistCreateModal: document.querySelector("#playlistCreateModal"),
  choosePlaylistModal: document.querySelector("#choosePlaylistModal"),
  choosePlaylistList: document.querySelector("#choosePlaylistList"),
  deletePlaylistModal: document.querySelector("#deletePlaylistModal"),
};

function normalize(value) {
  return String(value || "").toLowerCase().trim().replace(/\s+/g, " ");
}

function userKey(part) {
  return `road-music:${state.user?.email || "guest"}:${part}`;
}

function makeId(prefix) {
  return `${prefix}:${Date.now()}:${Math.random().toString(16).slice(2)}`;
}

function readStoredArray(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

function sanitizePlaylists(playlists) {
  return playlists
    .filter((playlist) => playlist && playlist.id !== "liked" && normalize(playlist.name) !== "liked songs")
    .map((playlist) => ({
      id: String(playlist.id || makeId("playlist")),
      name: String(playlist.name || "Untitled playlist").trim() || "Untitled playlist",
      tracks: Array.isArray(playlist.tracks) ? dedupeTracks(playlist.tracks) : [],
    }));
}

function dedupeTracks(tracks) {
  const seen = new Set();
  return tracks.filter((track) => {
    if (!track?.id || seen.has(track.id)) return false;
    seen.add(track.id);
    return true;
  });
}

function saveLibrary() {
  localStorage.setItem(userKey("playlists"), JSON.stringify(state.playlists));
  localStorage.setItem(userKey("active-playlist"), state.activePlaylistId || "");
  localStorage.setItem(userKey("queue"), JSON.stringify(state.queue));
}

function loadLibrary() {
  state.playlists = sanitizePlaylists(readStoredArray(userKey("playlists")));
  state.activePlaylistId = localStorage.getItem(userKey("active-playlist")) || "";

  if (!getActivePlaylist()) {
    state.activePlaylistId = state.playlists[0]?.id || "";
  }

  state.queue = readStoredArray(userKey("queue"));
  renderPlaylists();
  renderQueue();
  saveLibrary();
}

function getActivePlaylist() {
  return state.playlists.find((playlist) => playlist.id === state.activePlaylistId);
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
  return track?.artwork || DEFAULT_TRACK_ART;
}

function applyArtwork(img, track) {
  img.src = artworkFor(track);
  img.onerror = () => {
    img.onerror = null;
    img.src = DEFAULT_TRACK_ART;
  };
}

function renderTrackGrid(container, tracks, emptyMessage) {
  container.innerHTML = "";
  if (!tracks.length) {
    container.innerHTML = `<div class="empty-state">${emptyMessage}</div>`;
    return;
  }

  tracks.forEach((track, index) => {
    const node = els.template.content.firstElementChild.cloneNode(true);
    const art = node.querySelector(".track-art");
    const artButton = node.querySelector(".art-button");
    const isCurrent = state.currentTrack?.id === track.id && !els.audio.paused;

    applyArtwork(art, track);
    art.alt = `${track.title} cover`;
    node.querySelector("h4").textContent = track.title;
    node.querySelector("p").textContent = `${track.artist || "Unknown artist"}${track.album ? ` - ${track.album}` : ""}`;
    node.classList.toggle(PLAYING_CLASS, isCurrent);
    artButton.setAttribute("aria-label", isCurrent ? `Pause ${track.title}` : `Play ${track.title}`);
    artButton.addEventListener("click", () => toggleTrackFromCard(track, tracks, index));
    node.querySelector(".save-button").addEventListener("click", () => saveSongToPlaylist(track));
    node.querySelector(".queue-button").addEventListener("click", () => addToQueue(track));
    container.appendChild(node);
  });
}

function renderAllTrackLists() {
  renderTrackGrid(
    els.resultsGrid,
    state.results,
    "No full songs found in the cloud catalog. Add songs to songs.json or your cloud storage catalog."
  );
  const active = getActivePlaylist();
  renderTrackGrid(els.playlistGrid, active?.tracks || [], "This playlist is empty. Search for a song and press Save.");
  renderQueue();
}

function renderPlaylists() {
  els.playlistTabs.innerHTML = "";

  if (!state.playlists.length) {
    els.playlistTabs.innerHTML = `
      <div class="empty-state playlist-empty">
        Create your first playlist, then save songs into it from Discover.
      </div>
    `;
  }

  state.playlists.forEach((playlist) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `playlist-tab${playlist.id === state.activePlaylistId ? " active" : ""}`;
    button.innerHTML = `
      <span>${escapeHtml(playlist.name)}</span>
      <strong>${playlist.tracks.length} song${playlist.tracks.length === 1 ? "" : "s"}</strong>
    `;
    button.addEventListener("click", () => {
      state.activePlaylistId = playlist.id;
      renderPlaylists();
      saveLibrary();
    });
    els.playlistTabs.appendChild(button);
  });

  const active = getActivePlaylist();
  els.activePlaylistName.textContent = active?.name || "No playlist selected";
  els.deletePlaylist.disabled = !active;
  renderTrackGrid(els.playlistGrid, active?.tracks || [], "This playlist is empty. Search for a song and press Save.");
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return entities[char];
  });
}

function createPlaylist(name) {
  const trimmed = name.trim();
  els.playlistNameError.textContent = "";

  if (!trimmed) {
    els.playlistNameError.textContent = "Playlist name cannot be empty.";
    els.playlistNameInput.focus();
    return false;
  }

  const playlist = { id: makeId("playlist"), name: trimmed, tracks: [] };
  state.playlists.unshift(playlist);
  state.activePlaylistId = playlist.id;
  els.playlistNameInput.value = "";
  renderPlaylists();
  saveLibrary();
  showView("playlistView", document.querySelector('[data-view="playlistView"]'));
  els.statusText.textContent = `"${playlist.name}" created.`;
  return playlist;
}

function deleteActivePlaylist() {
  const active = getActivePlaylist();
  if (!active) return;

  state.playlists = state.playlists.filter((playlist) => playlist.id !== active.id);
  state.activePlaylistId = state.playlists[0]?.id || "";
  renderPlaylists();
  saveLibrary();
  closeModals();
  els.statusText.textContent = `"${active.name}" deleted.`;
}

function renderQueue() {
  renderTrackGrid(els.queueGrid, state.queue, "Your queue is empty. Search for a song and press Queue.");
}

function saveSongToPlaylist(track) {
  if (!state.user) {
    els.statusText.textContent = "Sign in first so Road-Music knows where to save your playlists.";
    return;
  }

  if (state.playlists.length === 0) {
    state.pendingSaveTrack = track;
    openCreatePlaylistModal(`Create a playlist first, then save "${track.title}".`);
    return;
  }

  if (state.playlists.length === 1) {
    addTrackToPlaylist(track, state.playlists[0]);
    return;
  }

  state.pendingSaveTrack = track;
  openChoosePlaylistModal(track);
}

function addTrackToPlaylist(track, playlist) {
  if (!playlist.tracks.some((item) => item.id === track.id)) {
    playlist.tracks.unshift(track);
    els.statusText.textContent = `"${track.title}" saved to ${playlist.name}.`;
  } else {
    els.statusText.textContent = `"${track.title}" is already in ${playlist.name}.`;
  }

  state.activePlaylistId = playlist.id;
  renderPlaylists();
  saveLibrary();
  closeModals();
}

function addToQueue(track) {
  if (!state.queue.some((item) => item.id === track.id)) {
    state.queue.push(track);
    els.statusText.textContent = `"${track.title}" added to queue.`;
  } else {
    els.statusText.textContent = `"${track.title}" is already in your queue.`;
  }
  renderQueue();
  saveLibrary();
}

async function playTrack(track, list = state.results, index = 0) {
  if (!track.audioUrl) {
    els.statusText.textContent = "This song does not have an audio URL in the catalog.";
    return;
  }

  if (state.currentTrack?.id !== track.id && state.currentTrack) {
    state.history.push(state.currentTrack);
  }

  state.currentTrack = track;
  state.currentList = list;
  state.currentIndex = index;
  els.audio.src = track.audioUrl;

  try {
    await els.audio.play();
    updatePlayer(track);
    renderAllTrackLists();
  } catch {
    els.statusText.textContent = "The browser could not play this song URL. Check cloud CORS/public access.";
  }
}

function toggleTrackFromCard(track, list, index) {
  if (state.currentTrack?.id === track.id) {
    togglePlay();
    return;
  }

  playTrack(track, list, index);
}

function updatePlayer(track) {
  els.playerTitle.textContent = track.title;
  els.playerArtist.textContent = track.artist || "Unknown artist";
  applyArtwork(els.playerArt, track);
  setPlayButtonState(!els.audio.paused);
}

function setPlayButtonState(isPlaying) {
  els.playButton.classList.toggle("pause-icon", isPlaying);
  els.playButton.classList.toggle("play-icon", !isPlaying);
  els.playButton.setAttribute("aria-label", isPlaying ? "Pause" : "Play");
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
  } else {
    els.audio.pause();
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
  closeSidebarOnMobile();
}

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function openModal(modal) {
  els.modalBackdrop.hidden = false;
  document.querySelectorAll(".modal").forEach((item) => {
    item.hidden = item !== modal;
  });
  requestAnimationFrame(() => els.modalBackdrop.classList.add("open"));
}

function closeModals(options = {}) {
  const { keepPendingTrack = false } = options;
  els.modalBackdrop.classList.remove("open");
  document.querySelectorAll(".modal").forEach((item) => {
    item.hidden = true;
  });
  els.modalBackdrop.hidden = true;
  els.playlistNameError.textContent = "";
  if (!keepPendingTrack) state.pendingSaveTrack = null;
}

function openCreatePlaylistModal(message = "") {
  els.playlistNameError.textContent = message;
  openModal(els.playlistCreateModal);
  setTimeout(() => els.playlistNameInput.focus(), 0);
}

function openChoosePlaylistModal(track) {
  els.choosePlaylistList.innerHTML = "";
  state.playlists.forEach((playlist) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "choose-playlist-button";
    button.innerHTML = `
      <span>${escapeHtml(playlist.name)}</span>
      <strong>${playlist.tracks.length} song${playlist.tracks.length === 1 ? "" : "s"}</strong>
    `;
    button.addEventListener("click", () => addTrackToPlaylist(track, playlist));
    els.choosePlaylistList.appendChild(button);
  });
  openModal(els.choosePlaylistModal);
}

function toggleSidebar() {
  const collapsed = document.body.classList.toggle("sidebar-collapsed");
  els.sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
}

function closeSidebarOnMobile() {
  if (window.matchMedia("(max-width: 860px)").matches) {
    document.body.classList.add("sidebar-collapsed");
    els.sidebarToggle.setAttribute("aria-expanded", "false");
  }
}

function wireEvents() {
  els.searchButton.addEventListener("click", () => searchSongs(els.searchInput.value));
  els.searchInput.addEventListener("input", debounce(() => searchSongs(els.searchInput.value), 320));
  els.searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") searchSongs(els.searchInput.value);
  });

  els.openCreatePlaylist.addEventListener("click", () => openCreatePlaylistModal());

  els.playlistForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const pendingTrack = state.pendingSaveTrack;
    const playlist = createPlaylist(els.playlistNameInput.value);
    if (!playlist) return;

    if (pendingTrack) {
      addTrackToPlaylist(pendingTrack, playlist);
      state.pendingSaveTrack = null;
    } else {
      closeModals();
    }
  });

  els.deletePlaylist.addEventListener("click", () => {
    if (getActivePlaylist()) openModal(els.deletePlaylistModal);
  });

  els.confirmDeletePlaylist.addEventListener("click", deleteActivePlaylist);

  els.playButton.addEventListener("click", togglePlay);
  els.nextButton.addEventListener("click", playNext);
  els.prevButton.addEventListener("click", playPrevious);
  els.sidebarToggle.addEventListener("click", toggleSidebar);

  els.audio.addEventListener("timeupdate", () => {
    const percent = els.audio.duration ? (els.audio.currentTime / els.audio.duration) * 100 : 0;
    els.progress.value = String(percent);
    els.currentTime.textContent = formatTime(els.audio.currentTime);
    els.duration.textContent = formatTime(els.audio.duration);
  });

  els.audio.addEventListener("ended", playNext);

  els.audio.addEventListener("pause", () => {
    setPlayButtonState(false);
    renderAllTrackLists();
  });

  els.audio.addEventListener("play", () => {
    setPlayButtonState(true);
    renderAllTrackLists();
  });

  els.progress.addEventListener("input", () => {
    if (els.audio.duration) {
      els.audio.currentTime = (Number(els.progress.value) / 100) * els.audio.duration;
    }
  });

  document.querySelectorAll(".nav-button").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.view, button));
  });

  document.querySelectorAll(".modal-close").forEach((button) => {
    button.addEventListener("click", closeModals);
  });

  els.modalBackdrop.addEventListener("click", (event) => {
    if (event.target === els.modalBackdrop) closeModals();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !els.modalBackdrop.hidden) closeModals();
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

  if (window.matchMedia("(max-width: 860px)").matches) {
    document.body.classList.add("sidebar-collapsed");
    els.sidebarToggle.setAttribute("aria-expanded", "false");
  }
});