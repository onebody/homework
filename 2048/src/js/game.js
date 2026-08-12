/**
 * 2048 Mobile H5 Game
 * Pure vanilla JavaScript, no dependencies
 */

(function () {
  'use strict';

  // ===== Game2048 Core Logic Class =====
  class Game2048 {
    constructor(size) {
      this.size = size || 4;
      this.board = [];
      this.score = 0;
      this.won = false;
      this.continueAfterWin = false;
      this.over = false;
      this._initEmptyBoard();
    }

    _initEmptyBoard() {
      this.board = [];
      for (var r = 0; r < this.size; r++) {
        var row = [];
        for (var c = 0; c < this.size; c++) {
          row.push(0);
        }
        this.board.push(row);
      }
    }

    init() {
      this._initEmptyBoard();
      this.score = 0;
      this.won = false;
      this.continueAfterWin = false;
      this.over = false;
      this._addRandomTile();
      this._addRandomTile();
    }

    _addRandomTile() {
      var emptyCells = [];
      for (var r = 0; r < this.size; r++) {
        for (var c = 0; c < this.size; c++) {
          if (this.board[r][c] === 0) {
            emptyCells.push({ r: r, c: c });
          }
        }
      }
      if (emptyCells.length === 0) return null;
      var cell = emptyCells[Math.floor(Math.random() * emptyCells.length)];
      var value = Math.random() < 0.9 ? 2 : 4;
      this.board[cell.r][cell.c] = value;
      return { row: cell.r, col: cell.c, value: value };
    }

    getBoard() {
      return this.board.map(function (row) { return row.slice(); });
    }

    getScore() {
      return this.score;
    }

    isGameOver() {
      return this.over;
    }

    hasWon() {
      return this.won;
    }

    canMove() {
      for (var r = 0; r < this.size; r++) {
        for (var c = 0; c < this.size; c++) {
          if (this.board[r][c] === 0) return true;
          if (c < this.size - 1 && this.board[r][c] === this.board[r][c + 1]) return true;
          if (r < this.size - 1 && this.board[r][c] === this.board[r + 1][c]) return true;
        }
      }
      return false;
    }

    move(direction) {
      if (this.over) return { moved: false, score: 0, mergedPositions: [], newTile: null };

      var oldBoard = this.board.map(function (row) { return row.slice(); });
      var mergedPositions = [];
      var moveScore = 0;

      // Transform board so we always process as "left"
      var workingBoard = this._rotateBoard(this.board, direction);

      for (var r = 0; r < this.size; r++) {
        var result = this._slideAndMergeRow(workingBoard[r]);
        workingBoard[r] = result.row;
        moveScore += result.score;
        // Track merged positions (in rotated coordinates)
        for (var i = 0; i < result.mergedIndices.length; i++) {
          mergedPositions.push({ row: r, col: result.mergedIndices[i] });
        }
      }

      // Rotate back
      this.board = this._rotateBack(workingBoard, direction);

      // Convert merged positions back to original coordinates
      var originalMerged = this._convertMergedPositions(mergedPositions, direction);

      var moved = !this._boardsEqual(oldBoard, this.board);
      var newTile = null;

      if (moved) {
        this.score += moveScore;
        newTile = this._addRandomTile();

        // Check win
        if (!this.won && this._containsValue(2048)) {
          this.won = true;
        }
      }

      // Check game over (regardless of whether this move changed the board)
      if (!this.canMove()) {
        this.over = true;
      }

      return {
        moved: moved,
        score: moveScore,
        mergedPositions: originalMerged,
        newTile: newTile
      };
    }

    _slideAndMergeRow(row) {
      var size = this.size;
      var filtered = row.filter(function (v) { return v !== 0; });
      var merged = [];
      var mergedIndices = [];
      var score = 0;
      var i = 0;

      while (i < filtered.length) {
        if (i + 1 < filtered.length && filtered[i] === filtered[i + 1]) {
          var newValue = filtered[i] * 2;
          merged.push(newValue);
          mergedIndices.push(merged.length - 1);
          score += newValue;
          i += 2;
        } else {
          merged.push(filtered[i]);
          i++;
        }
      }

      while (merged.length < size) {
        merged.push(0);
      }

      return { row: merged, score: score, mergedIndices: mergedIndices };
    }

    _rotateBoard(board, direction) {
      var size = this.size;
      var result = [];

      if (direction === 'left') {
        return board.map(function (row) { return row.slice(); });
      }

      if (direction === 'right') {
        return board.map(function (row) { return row.slice().reverse(); });
      }

      if (direction === 'up') {
        // Transpose: columns become rows (top to bottom)
        for (var c = 0; c < size; c++) {
          var newRow = [];
          for (var r = 0; r < size; r++) {
            newRow.push(board[r][c]);
          }
          result.push(newRow);
        }
        return result;
      }

      if (direction === 'down') {
        // Transpose and reverse each row (bottom to top)
        for (var c = 0; c < size; c++) {
          var newRow = [];
          for (var r = size - 1; r >= 0; r--) {
            newRow.push(board[r][c]);
          }
          result.push(newRow);
        }
        return result;
      }

      return board.map(function (row) { return row.slice(); });
    }

    _rotateBack(board, direction) {
      var size = this.size;
      var result = [];

      if (direction === 'left') {
        return board.map(function (row) { return row.slice(); });
      }

      if (direction === 'right') {
        return board.map(function (row) { return row.slice().reverse(); });
      }

      if (direction === 'up') {
        // Transpose back
        for (var r = 0; r < size; r++) {
          var newRow = [];
          for (var c = 0; c < size; c++) {
            newRow.push(board[c][r]);
          }
          result.push(newRow);
        }
        return result;
      }

      if (direction === 'down') {
        // Inverse of forward transform: board[r][c] = transformed[c][size-1-r]
        for (var r = 0; r < size; r++) {
          var newRow = [];
          for (var c = 0; c < size; c++) {
            newRow.push(board[c][size - 1 - r]);
          }
          result.push(newRow);
        }
        return result;
      }

      return board.map(function (row) { return row.slice(); });
    }

    _convertMergedPositions(mergedPositions, direction) {
      var size = this.size;
      var result = [];

      for (var i = 0; i < mergedPositions.length; i++) {
        var pos = mergedPositions[i];
        var r = pos.row;
        var c = pos.col;

        if (direction === 'left') {
          result.push({ row: r, col: c });
        } else if (direction === 'right') {
          result.push({ row: r, col: size - 1 - c });
        } else if (direction === 'up') {
          result.push({ row: c, col: r });
        } else if (direction === 'down') {
          result.push({ row: size - 1 - c, col: r });
        }
      }

      return result;
    }

    _boardsEqual(a, b) {
      for (var r = 0; r < this.size; r++) {
        for (var c = 0; c < this.size; c++) {
          if (a[r][c] !== b[r][c]) return false;
        }
      }
      return true;
    }

    _containsValue(value) {
      for (var r = 0; r < this.size; r++) {
        for (var c = 0; c < this.size; c++) {
          if (this.board[r][c] === value) return true;
        }
      }
      return false;
    }

    serialize() {
      return {
        board: this.board.map(function (row) { return row.slice(); }),
        score: this.score,
        won: this.won,
        continueAfterWin: this.continueAfterWin,
        over: this.over
      };
    }

    static deserialize(data) {
      var game = new Game2048(data.board.length);
      game.board = data.board.map(function (row) { return row.slice(); });
      game.score = data.score;
      game.won = data.won || false;
      game.continueAfterWin = data.continueAfterWin || false;
      game.over = data.over || false;
      return game;
    }
  }

  // ===== Renderer & Controller =====
  var STORAGE_KEY = 'game2048_state';
  var BEST_SCORE_KEY = 'game2048_best';

  var game = null;
  var bestScore = 0;

  // DOM elements (initialized in init())
  var boardEl, tileContainer, scoreEl, bestScoreEl;
  var overlayEl, overlayMessageEl, btnContinue, btnRetry, btnNewGame;

  // ===== Initialization =====
  function init() {
    boardEl = document.getElementById('game-board');
    tileContainer = document.getElementById('tile-container');
    scoreEl = document.getElementById('score');
    bestScoreEl = document.getElementById('best-score');
    overlayEl = document.getElementById('overlay');
    overlayMessageEl = document.getElementById('overlay-message');
    btnContinue = document.getElementById('btn-continue');
    btnRetry = document.getElementById('btn-retry');
    btnNewGame = document.getElementById('btn-new-game');

    bestScore = parseInt(localStorage.getItem(BEST_SCORE_KEY) || '0', 10);
    loadGame();
    render();
    bindEvents();
  }

  function loadGame() {
    var saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        var data = JSON.parse(saved);
        if (data.board && data.board.length === 4) {
          game = Game2048.deserialize(data);
          return;
        }
      } catch (e) {
        // Invalid save, start fresh
      }
    }
    game = new Game2048(4);
    game.init();
    saveGame();
  }

  function saveGame() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(game.serialize()));
    if (game.getScore() > bestScore) {
      bestScore = game.getScore();
      localStorage.setItem(BEST_SCORE_KEY, String(bestScore));
    }
  }

  // ===== Rendering =====
  function render(mergedPositions, newTile) {
    var board = game.getBoard();
    tileContainer.innerHTML = '';

    var mergedSet = {};
    if (mergedPositions) {
      for (var i = 0; i < mergedPositions.length; i++) {
        var p = mergedPositions[i];
        mergedSet[p.row + '-' + p.col] = true;
      }
    }

    for (var r = 0; r < 4; r++) {
      for (var c = 0; c < 4; c++) {
        var value = board[r][c];
        if (value === 0) continue;

        var tile = document.createElement('div');
        tile.className = 'tile tile-' + (value > 2048 ? 'super' : value);
        tile.classList.add('row-' + r);
        tile.classList.add('col-' + c);
        tile.textContent = value;

        if (newTile && newTile.row === r && newTile.col === c) {
          tile.classList.add('new');
        }
        if (mergedSet[r + '-' + c]) {
          tile.classList.add('merged');
        }

        tileContainer.appendChild(tile);
      }
    }

    scoreEl.textContent = game.getScore();
    bestScoreEl.textContent = bestScore;

    updateOverlay();
  }

  function updateOverlay() {
    overlayEl.classList.remove('show', 'win');
    btnContinue.style.display = 'none';

    if (game.isGameOver()) {
      overlayEl.classList.add('show');
      overlayMessageEl.textContent = '游戏结束！';
      btnRetry.textContent = '再来一局';
    } else if (game.hasWon() && !game.continueAfterWin) {
      overlayEl.classList.add('show', 'win');
      overlayMessageEl.textContent = '你赢了！';
      btnContinue.style.display = 'inline-block';
      btnRetry.textContent = '新游戏';
    }
  }

  // ===== Game Actions =====
  function handleMove(direction) {
    if (!game) return;

    var result = game.move(direction);
    if (result.moved) {
      saveGame();
      render(result.mergedPositions, result.newTile);

      if (result.score > 0) {
        scoreEl.classList.add('bump');
        setTimeout(function () {
          scoreEl.classList.remove('bump');
        }, 200);
      }
    }
  }

  function newGame() {
    game = new Game2048(4);
    game.init();
    saveGame();
    render();
  }

  function continueGame() {
    game.continueAfterWin = true;
    saveGame();
    overlayEl.classList.remove('show', 'win');
  }

  // ===== Touch Handling =====
  var touchStartX = 0;
  var touchStartY = 0;
  var touchActive = false;
  var SWIPE_THRESHOLD = 30;

  function onTouchStart(e) {
    if (e.touches.length !== 1) return;
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
    touchActive = true;
  }

  function onTouchMove(e) {
    if (touchActive) {
      e.preventDefault();
    }
  }

  function onTouchEnd(e) {
    if (!touchActive) return;
    touchActive = false;

    var touchEndX = e.changedTouches[0].clientX;
    var touchEndY = e.changedTouches[0].clientY;
    var dx = touchEndX - touchStartX;
    var dy = touchEndY - touchStartY;
    var absDx = Math.abs(dx);
    var absDy = Math.abs(dy);

    if (Math.max(absDx, absDy) < SWIPE_THRESHOLD) return;

    if (absDx > absDy) {
      handleMove(dx > 0 ? 'right' : 'left');
    } else {
      handleMove(dy > 0 ? 'down' : 'up');
    }
  }

  // ===== Keyboard Handling =====
  function onKeyDown(e) {
    var keyMap = {
      ArrowUp: 'up',
      ArrowDown: 'down',
      ArrowLeft: 'left',
      ArrowRight: 'right',
      w: 'up',
      s: 'down',
      a: 'left',
      d: 'right',
      W: 'up',
      S: 'down',
      A: 'left',
      D: 'right'
    };

    var direction = keyMap[e.key];
    if (direction) {
      e.preventDefault();
      handleMove(direction);
    }
  }

  // ===== Event Binding =====
  function bindEvents() {
    boardEl.addEventListener('touchstart', onTouchStart, { passive: true });
    boardEl.addEventListener('touchmove', onTouchMove, { passive: false });
    boardEl.addEventListener('touchend', onTouchEnd, { passive: true });

    document.addEventListener('keydown', onKeyDown);

    btnNewGame.addEventListener('click', function (e) {
      e.preventDefault();
      newGame();
    });

    btnRetry.addEventListener('click', function (e) {
      e.preventDefault();
      newGame();
    });

    btnContinue.addEventListener('click', function (e) {
      e.preventDefault();
      continueGame();
    });
  }

  // ===== Export for testing =====
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Game2048;
  }

  // ===== Start =====
  if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', init);
  }
})();
