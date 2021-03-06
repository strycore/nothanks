#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, render_template, session  # , request, make_response
from flask.ext.socketio import SocketIO, emit

from uuid import uuid4
import engine

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secretkey'
app.debug = True
socketio = SocketIO(app)
nicks = {}


@app.route('/')
def index():
    # resp = make_response(render_template('nothanks.html'))
    # if not request.cookies.get('nothanks'):
    #    resp.set_cookie('nothanks', uuid4().hex)
    print('session: %s' % session)
    if 'uuid' not in session:
        session['uuid'] = uuid4().hex
    return render_template('nothanks.html')
#    return resp


@socketio.on('chatinput', namespace='/chat')
def chat_send_msg(msg):
    emit('chatoutput',
         {'data': '%s: %s' % (session['nick'], msg['data'])}, broadcast=True)


@socketio.on('nickinput', namespace='/chat')
def chat_update_nick(msg):
    nick = msg['data']
    if nick in nicks.values():
        emit('chatoutput', {'data': 'This nickname is already in use.'})
        emit('nickoutput', {'data': session['nick']})
    elif 3 > len(nick) or 16 < len(nick):
        emit('chatoutput',
             {'data': 'Your nickname is either too short or too long.'})
        emit('nickoutput', {'data': session['nick']})
    elif " " in nick:
        emit('chatoutput', {'data': 'Your nickname must not contain spaces.'})
        emit('nickoutput', {'data': session['nick']})
    else:
        # try:
        #     nicks.pop({nicks[k]:k for k in nicks}[session['nick']])
        # except KeyError:
        #     pass
        emit('chatoutput',
             {'data': '%s is now known as %s.' % (session['nick'], nick)},
             broadcast=True)
        session['nick'] = nick
        if nick in game.players_by_uuid:
            game.players_by_uuid[session['nick']].name = nick
        if game.started:
            emit_game_infos(False)
        nicks[session['uuid']] = nick
        emit('nickoutput', {'data': session['nick']})
        chat_update_nicklist()


@socketio.on('connect', namespace='/chat')
def chat_connect():
    uuid = session['uuid']
    if uuid in nicks:
        session['nick'] = nicks[uuid]
    if 'nick' not in session:
        num = len(nicks)
        while ("player%i" % num) in nicks.values():
            num += 1
        session['nick'] = "player%i" % num
    nicks[uuid] = session['nick']
    print('%s connected (%s)' % (uuid, session['nick']))
    emit('chatoutput',
         {'data': '%s joined the room.' % session['nick']}, broadcast=True)
    emit('nickoutput', {'data': session['nick']})
    emit('uuid', {'uuid': session['uuid']})
    chat_update_nicklist()


@socketio.on('connect', namespace='/game')
def game_connect():
    print('in game_connect')
    print('players uuid: %s' % ([p.uuid for p in game.players],))
    print('nicks: %s ' % nicks)
    emit('gameplayers',
         {'players': [(p.uuid, nicks[p.uuid]) for p in game.players]},
         broadcast=True)
    if game.started:
        emit('cards_update',
             {'hands': {p.uuid: p.group_successive() for p in game.players}},
             broadcast=True)
        emit('cardup', {'card': game.cardup}, broadcast=True)
        emit('coinstatus',
             {
                 'game': game.coins,
                 'players': {p.uuid: p.coins for p in game.players}
             },
             broadcast=True)
        emit('scores',
             {'scores': {p.uuid: p.score for p in game.players}},
             broadcast=True)
        emit('nextplayer', {'player': game.nextplayer.uuid}, broadcast=True)


@socketio.on('disconnect', namespace='/chat')
def chat_disconnect():
    print('%s disconnected (%s)' % (session['uuid'], session['nick']))
    print('nicks is now: %s' % nicks)
    # try:
    #     nicks.pop({nicks[k]:k for k in nicks}[session['nick']])
    # except KeyError:
    #     pass
    emit('chatoutput',
         {'data': '%s left the room.' % session['nick']},
         broadcast=True)
    chat_update_nicklist()


@socketio.on('debug', namespace='/game')
def game_debug():
    emit('gameoutput',
         {'text': '\nStarted: %s\n%s\n%s' % (game.started, game.players, game)})


@socketio.on('play', namespace='/game')
def game_join():
    print('in game_join')
    if 'uuid' not in session:
        print('had no uuid adding one')
        session['uuid'] = uuid4().hex
    if not session['uuid'] in [p.uuid for p in game.players]:
        game.addplayer(name=session['nick'], uuid=session['uuid'])
        emit('gameoutput',
             {'text': '%s has joined the game.' % session['nick']},
             broadcast=True)
        print('players uuid: %s' % ([p.uuid for p in game.players],))
        print(nicks)
        print('nicks: %s ' % nicks)
        emit('gameplayers',
             {'players': [(p.uuid, nicks[p.uuid]) for p in game.players]},
             broadcast=True)
        # print([(p.uuid, nicks[p.uuid]) for p in game.players ])
        chat_update_nicklist()
    else:
        emit('gameoutput', {'text': 'You are already playing.'})


@socketio.on('start', namespace='/game')
def game_start():
    if not game.started:
        if len(game.players) >= 2:
            game.start()
            emit('cardup', {'card': game.cardup}, broadcast=True)
            emit('gameoutput', {'text': '%s' % game}, broadcast=True)
            emit_game_infos(False)
        else:
            emit('gameoutput', {'text': 'Not enough players'})
    else:
        emit('gameoutput', {'text': 'Game is already started.'})


@socketio.on('stop', namespace='/game')
def game_stop():
    if game.started:
        player_scores = game.end()
        print('players scores: %s' % player_scores)
        winner, winner_points = sorted(player_scores.items(),
                                       key=lambda i: i[1])[0]
        print('thewinneriz: %s' % winner)
        emit('gamewinner', {'winner': winner}, broadcast=True)
        emit('gameoutput',
             {'text': 'The winner is %s' % winner},
             broadcast=True)
    else:
        emit('gameoutput', {'text': 'Game is not started.'})


@socketio.on('action', namespace='/game')
def game_pick(msg):
    action = msg['data']
    out = True
    if game.started:
        current_player_uuid = game.nextplayer.uuid
        current_card = game.cardup
        if current_player_uuid == session['uuid']:
            if action == 'pick':
                out = game.play(False)
                emit('cardpick',
                     {'player': current_player_uuid, 'card': current_card},
                     broadcast=True)
                emit('cardup', {'card': '%s' % game.cardup}, broadcast=True)
                emit('scores',
                     {'scores': {p.uuid: p.score for p in game.players}},
                     broadcast=True)
            elif action == 'pass':
                if game.nextplayer.coins == 0:
                    emit('gameoutput',
                         {'text': 'You shall not pass (no coins left).'})
                else:
                    out = game.play(True)
            emit('coinstatus',
                 {
                     'game': game.coins,
                     'players': {p.uuid: p.coins for p in game.players}
                 },
                 broadcast=True)
            emit('gameoutput', {'text': '%s' % game}, broadcast=True)
            emit('nextplayer', {'player': game.nextplayer.uuid}, broadcast=True)
#            cardnum = game.nextplayer.group_successive()
#            emit('cards_update_old', {'cardnum': cardnum}, broadcast=True)
            emit_game_infos(True)
            if not out:
                game_stop()
        else:
            emit('gameoutput', {'text': 'This is not your turn'})
    else:
        emit('gameoutput', {'text': 'Game is non started yet.'})


def chat_update_nicklist():
    print(nicks)
    nicks2 = [
        ('*%s' if n in [p.name for p in game.players] else '%s') % n
        for n in nicks.values()
    ]
    print(nicks2)
    msg = "\n".join(nicks2)
    emit('nicklistupdate', {'data': msg}, broadcast=True)


def emit_game_infos(private=False):
    emit('gameinfo',
         {
             'card': '%s' % game.cardup,
             'bonus': '%s' % game.coins,
             'nextplayer': '%s' % game.nextplayer.name
         },
         broadcast=True)
    if private:
        player = game.players_by_uuid[session['uuid']]
        emit('gameinfo_private',
             {
                 'score': '%s' % player.update_score(),
                 'coins': '%s' % player.coins,
                 'cards': {p.name: p.cards for p in game.players},
             })


if __name__ == '__main__':
    game = engine.Game(nplayer=0)
    socketio.run(app, host='0.0.0.0')
