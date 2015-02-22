
class WSRC_team
  constructor: (@player1, @player2) ->
    @primary_id = @player1.id
    @secondary_id = if @players then "#{ @player1.id }_#{ @player2.id }" else "#{ @player1.id }"

  has_player: (player_id) ->
    if @player1.id == player_id
      return true
    return @player2 and @player2.id == player_id
    
  toString: () ->
    if this.player2
      return  "#{ @player1.short_name } & #{ @player2.short_name }"
    return @player1.full_name

window.WSRC_team = WSRC_team