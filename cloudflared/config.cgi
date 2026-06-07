#!/usr/bin/perl
use strict;
use warnings;
use WebminCore;
our (%config, %in, %gconfig);
init_config();
ReadParse();

my $config_file = $config{'config_file'} || "";
my $cloudflared_bin = $config{'cloudflared'} || "";

my @cfg = ("/etc/cloudflared/config.yml","/etc/cloudflared/config.yaml","$ENV{HOME}/.cloudflared/config.yml","/root/.cloudflared/config.yml");
my @bin = ("/usr/local/bin/cloudflared","/usr/bin/cloudflared");
sub ff { for (@_) { return $_ if -f } return undef }
sub fb { for (@_) { return $_ if -x } my $w = `which cloudflared 2>&1`; chomp $w; return $w if $w && -x $w; return undef }
if (!$config_file) { $config_file = ff(@cfg) || $cfg[0] }
if (!$cloudflared_bin) { $cloudflared_bin = fb(@bin) || "/usr/local/bin/cloudflared" }

my $dc = ff(@cfg); my $db = fb(@bin); my $be = -x $cloudflared_bin;
my $action = $in{'action'} || ''; my $tunnel = $in{'tunnel'} || '';

sub msg {
    my ($t, $text) = @_;
    my ($bg, $fg, $bd) = $t eq "ok" ? ("#d4edda","#155724","#c3e6cb") : ("#f8d7da","#721c24","#f5c6cb");
    print "<div style='margin:15px 0; padding:10px; background:$bg; color:$fg; border:1px solid $bd; border-radius:4px;'>$text</div>";
}
sub btn { my ($u, $t) = @_; return "<a class='ui_button' href='$u'>$t</a>" }

&ui_print_header(undef, "Cloudflared Settings", "", undef, 1);

if ($in{'save_settings'}) {
    &open_lock_config();
    $config{'config_file'} = $in{'config_file'} || "";
    $config{'cloudflared'} = $in{'cloudflared'} || "";
    &save_config();
    print "<meta http-equiv='refresh' content='0;url=config.cgi'>";
    msg("ok", "Settings saved."); print &ui_hr();
}

if ($action eq "create" && $in{'tunnel_name'}) {
    my $n = $in{'tunnel_name'}; $n =~ s/[^a-zA-Z0-9_-]//g;
    if ($n) {
        my $r = `$cloudflared_bin tunnel create $n 2>&1`;
        if ($?) { msg("err", "Failed to create tunnel: $r") }
        else {
            msg("ok", "Tunnel '$n' created successfully.");
            my $cf = ""; if ($r =~ /credentials file at\s+(.+)$/m) { $cf = $1 } elsif ($r =~ /Written credentials file to\s+(.+)$/m) { $cf = $1 }
            if ($cf) { $cf =~ s/\s+$//; my $cp = "/etc/cloudflared/$n.yml";
                unless (-f $cp) { open(my $fh,'>',$cp); print $fh "# Tunnel: $n\ntunnel: $n\ncredentials-file: $cf\n\n"; close $fh; msg("ok","Created config: $cp") }
                unless (-f "/etc/systemd/system/cloudflared-tunnel-$n.service") {
                    open(my $fh,'>',"/etc/systemd/system/cloudflared-tunnel-$n.service");
                    print $fh "[Unit]\nDescription=Cloudflared Tunnel $n\nAfter=network.target\n\n[Service]\nType=simple\nExecStart=$cloudflared_bin tunnel run $n\nRestart=on-failure\nRestartSec=5\n\n[Install]\nWantedBy=multi-user.target\n";
                    close $fh; `systemctl daemon-reload 2>&1`; msg("ok","Created service: cloudflared-tunnel-$n")
                }
            }
        }
    } else { msg("err", "Invalid tunnel name.") }
    print &ui_hr()
}

if ($action eq "delete" && $tunnel) {
    my $t = $tunnel; $t =~ s/[^a-zA-Z0-9_-]//g;
    if ($t && $in{'confirm'} eq "yes") {
        my $r = `$cloudflared_bin tunnel delete $t 2>&1`;
        msg($? ? "err" : "ok", $? ? $r : "Tunnel '$t' deleted.");
        unlink "/etc/cloudflared/$t.yml" if -f "/etc/cloudflared/$t.yml";
        unlink "/etc/systemd/system/cloudflared-tunnel-$t.service" if -f "/etc/systemd/system/cloudflared-tunnel-$t.service";
        `systemctl daemon-reload 2>&1`
    } else {
        &ui_print_header(undef, "Confirm Delete", "", undef, 1);
        &ui_confirm("Delete tunnel '<b>$t</b>'? This will delete its config and systemd service.", "config.cgi?action=delete&tunnel=$t&confirm=yes", "config.cgi", "Yes, Delete", "Cancel");
        &ui_print_footer("index.cgi", "Back"); exit
    }
    print &ui_hr()
}

print &ui_form_start("config.cgi", "post");
print &ui_table_start("Module Settings", "width=80%");
print &ui_table_row("Cloudflared Binary", &ui_textbox("cloudflared",$cloudflared_bin,50).($db ? " <span style='color:green;font-size:10px;'>(detected: $db)</span>" : " <span style='color:red;font-size:10px;'>(not detected)</span>"));
print &ui_table_row("Config File", &ui_textbox("config_file",$config_file,50).($dc ? " <span style='color:green;font-size:10px;'>(detected: $dc)</span>" : " <span style='color:orange;font-size:10px;'>(not detected)</span>"));
print &ui_table_end();
print &ui_form_end([ ["save_settings","Save Settings"] ]);

print &ui_hr(); print "<h3>Create New Tunnel</h3>\n";
if ($be) {
    print &ui_form_start("config.cgi","get");
    print &ui_table_start("Create Tunnel","width=60%");
    print &ui_table_row("Tunnel Name", &ui_textbox("tunnel_name","",30)." <i>(letters, numbers, hyphens, underscores)</i>");
    print &ui_table_end();
    print &ui_form_end([ ["action=create","Create Tunnel"] ])
} else { msg("err", "Cloudflared binary not found.") }

print &ui_hr(); print "<h3>Configured Tunnels</h3>\n";
my @cf; my $cd = "/etc/cloudflared";
if (-d $cd) { opendir(my $dh, $cd); for (readdir($dh)) { next if !/\.ya?ml$/; push @cf, { name=>$_, path=>"$cd/$_" } } closedir $dh; @cf = sort { $a->{name} cmp $b->{name} } @cf }

if (@cf) {
    print &ui_table_start("Config Files","width=95%");
    &ui_columns_start(["File","Path","Actions"],["20%","50%","30%"]);
    for (@cf) { my $n = $_->{name}; $n =~ s/\.ya?ml$//;
        &ui_columns_row([ $n, $_->{path}, btn("config.cgi?edit=$n","Edit")." ".btn("index.cgi?action=start_tunnel&tunnel=$n","Start")." ".btn("config.cgi?action=delete&tunnel=$n","Delete") ])
    }
    &ui_columns_end(); print &ui_table_end()
} else { msg("err", "No config files in $cd.") }

my $et = $in{'edit'} || $tunnel;
if ($et) {
    $et =~ s/[^a-zA-Z0-9_-]//g;
    my $ep = "$cd/$et.yml"; $ep = "$cd/$et.yaml" if !-f $ep;
    print &ui_hr(); print "<h3>Editing Config: $et</h3>\n";
    if ($in{'save'}) { if (open(my $fh,'>',$ep)) { print $fh $in{'content'}; close $fh; msg("ok","Saved $ep") } else { msg("err","Failed: $!") } print &ui_hr() }
    if (-f $ep) { my $c = ""; if (open(my $fh,'<',$ep)) { local $/; $c = <$fh>; close $fh }
        print &ui_form_start("config.cgi","post"); print &ui_hidden("edit",$et);
        print &ui_table_start("Editing: $ep","width=95%");
        print &ui_table_row("", &ui_textarea("content",$c,30,100));
        print &ui_table_end(); print &ui_form_end([["save","Save Config"]]);
        print btn("index.cgi?action=start_tunnel&tunnel=$et","Start this Tunnel")." ".btn("logs.cgi?service=cloudflared-tunnel-$et","View Logs")
    } else { msg("err", "File not found.") }
}

if (-f $config_file && !$et) {
    print &ui_hr(); print "<h3>Default Config File</h3>\n";
    if ($in{'save-default'}) { if (open(my $fh,'>',$config_file)) { print $fh $in{'content'}; close $fh; msg("ok","Saved $config_file") } else { msg("err","Failed: $!") } print &ui_hr() }
    my $c = ""; if (open(my $fh,'<',$config_file)) { local $/; $c = <$fh>; close $fh }
    else { $c = "# Cloudflared configuration\n# See https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/configure-tunnels/config/\n\ntunnel: my-tunnel\ncredentials-file: /etc/cloudflared/credentials.json\n\n" }
    print &ui_form_start("config.cgi","post");
    print &ui_table_start("Editing: $config_file","width=95%");
    print &ui_table_row("", &ui_textarea("content",$c,30,100));
    print &ui_table_end(); print &ui_form_end([["save-default","Save Default Config"]])
}

&ui_print_footer("index.cgi", "Back to Manager");
